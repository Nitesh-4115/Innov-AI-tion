"""
Chat API Router
Endpoints for AI-powered chat interactions with the multi-agent system
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, time, date, timedelta
from zoneinfo import ZoneInfo
import re
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import json
import asyncio

from api.deps import get_db, services
import models
from database import get_db_context


router = APIRouter(prefix="/chat", tags=["chat"])


def _format_scheduled_time_for_patient(scheduled_time, patient_tz: str) -> str:
    """Return a formatted local time string for a scheduled_time which may be a datetime or string."""
    try:
        if not scheduled_time:
            return 'unknown'
        if isinstance(scheduled_time, str):
            # try parse common ISO or HH:MM formats
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%H:%M"):
                try:
                    dt = datetime.strptime(scheduled_time, fmt)
                    # if parsed as time-only, combine with today's date
                    if fmt == "%H:%M":
                        dt = datetime.combine(date.today(), dt.time())
                    return dt.replace(tzinfo=ZoneInfo('UTC')).astimezone(ZoneInfo(patient_tz)).strftime('%Y-%m-%d %H:%M')
                except Exception:
                    continue
            return scheduled_time
        # assume datetime-like
        if hasattr(scheduled_time, 'astimezone'):
            tz = ZoneInfo(patient_tz) if patient_tz else ZoneInfo('UTC')
            return scheduled_time.astimezone(tz).strftime('%Y-%m-%d %H:%M')
        return str(scheduled_time)
    except Exception:
        return 'unknown'


# ==================== REQUEST/RESPONSE SCHEMAS ====================

class ChatMessage(BaseModel):
    """Single chat message"""
    role: str = Field(..., description="Role: user, assistant, system")
    content: str = Field(..., min_length=1)
    timestamp: Optional[str] = None


class ChatRequest(BaseModel):
    """Request for chat interaction"""
    patient_id: int
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_history: Optional[List[ChatMessage]] = Field(default_factory=list)
    include_context: bool = Field(default=True, description="Include patient context")


class ChatResponse(BaseModel):
    """Response from chat"""
    patient_id: int
    response: str
    agent_used: Optional[str] = None
    actions_taken: Optional[List[Dict[str, Any]]] = None
    suggestions: Optional[List[str]] = None
    timestamp: str


class QuickAction(BaseModel):
    """Quick action for chat"""
    action: str = Field(..., description="Action type")
    patient_id: int
    parameters: Optional[Dict[str, Any]] = None


class QuickActionResponse(BaseModel):
    """Response from quick action"""
    success: bool
    action: str
    result: Dict[str, Any]
    message: str


def _infer_times_from_frequency(frequency: str, patient: Optional[models.Patient] = None) -> List[time]:
    """Map common frequency phrases to sensible time slots using patient preferences."""
    # Use patient preferences if available, else defaults
    breakfast = time(8, 0)
    lunch = time(12, 0)
    dinner = time(19, 0)
    bedtime = time(21, 0)
    
    if patient:
        if patient.breakfast_time:
            breakfast = patient.breakfast_time if isinstance(patient.breakfast_time, time) else time(*[int(x) for x in str(patient.breakfast_time).split(":")[:2]])
        if patient.lunch_time:
            lunch = patient.lunch_time if isinstance(patient.lunch_time, time) else time(*[int(x) for x in str(patient.lunch_time).split(":")[:2]])
        if patient.dinner_time:
            dinner = patient.dinner_time if isinstance(patient.dinner_time, time) else time(*[int(x) for x in str(patient.dinner_time).split(":")[:2]])
        if patient.sleep_time:
            sleep = patient.sleep_time if isinstance(patient.sleep_time, time) else time(*[int(x) for x in str(patient.sleep_time).split(":")[:2]])
            # Bedtime is 30 mins before sleep
            bedtime = time(sleep.hour, sleep.minute - 30) if sleep.minute >= 30 else time(sleep.hour - 1, sleep.minute + 30)
    
    freq = frequency.lower()
    if any(key in freq for key in ["three", "tid", "3x", "3 times"]):
        return [breakfast, lunch, dinner]
    if any(key in freq for key in ["twice", "bid", "2x", "2 times", "two"]):
        return [breakfast, dinner]
    if any(key in freq for key in ["evening", "night", "bed"]):
        return [bedtime]
    # Default: once daily at breakfast time
    return [breakfast]


def _parse_explicit_times(message: str) -> List[time]:
    """Extract explicit times like 10:00 AM, 21:30, 7pm."""
    slots: List[time] = []
    for match in re.finditer(r"(\d{1,2}:\d{2}\s*(am|pm)?)", message, re.IGNORECASE):
        raw = match.group(1).strip().lower()
        try:
            fmt = "%I:%M%p" if "am" in raw or "pm" in raw else "%H:%M"
            parsed = datetime.strptime(raw.replace(" ", ""), fmt).time()
            slots.append(parsed)
        except Exception:
            continue
    # Remove duplicates while preserving order
    unique = []
    seen = set()
    for t in slots:
        key = (t.hour, t.minute)
        if key not in seen:
            seen.add(key)
            unique.append(t)
    return unique


def _parse_unlabeled_med_line(message: str) -> Optional[Dict[str, str]]:
    """Handle comma-separated lines like 'Lisinopril, 10mg, once daily at 15:00' or
    unlabeled phrases that include a dosage and frequency.
    """
    # Accept common unlabeled formats: require at least a dosage and a frequency phrase
    dosage_match = re.search(r"(\d+\s?(mg|mcg|g|ml|units))", message, re.IGNORECASE)
    freq_match = re.search(r"(once daily|twice daily|three times daily|3x daily|bid|tid|daily|morning|evening|night|bedtime)", message, re.IGNORECASE)
    if not (dosage_match and freq_match):
        return None

    dosage = dosage_match.group(1).strip()
    frequency = freq_match.group(1).strip()

    # Assume the medication name is the first token or first comma-separated part
    parts = [p.strip() for p in re.split(r",|;", message) if p.strip()]
    name = parts[0] if parts else None
    # Clean common noise words
    if name:
        name = re.sub(r"^(please\s+)?(add\s+)?(medication\s+|med\s+)?", "", name, flags=re.IGNORECASE).strip()

    return {"name": name, "dosage": dosage, "frequency": frequency} if (name and dosage and frequency) else None


async def _process_add_med_activity(activity_id: int):
    """Background processor for queued add_medication AgentActivity."""
    try:
        with get_db_context() as db:
            act = db.query(models.AgentActivity).filter(models.AgentActivity.id == activity_id).first()
            if not act:
                return False
            if act.is_successful:
                return True

            input_data = act.input_data or {}
            name = input_data.get('name') or input_data.get('medication') or input_data.get('med')
            dosage = input_data.get('dosage') or input_data.get('dose')
            frequency = input_data.get('frequency') or input_data.get('freq') or 'once daily'
            times = input_data.get('times') or input_data.get('recurring_times') or []

            # Try to infer times from source message if missing
            if not times:
                src = input_data.get('source_message') or ''
                # reuse local parser
                parsed = _parse_explicit_times(src)
                if parsed:
                    times = [t.strftime('%H:%M') for t in parsed]

            medication_service = services.get_medication_service()
            schedule_service = services.get_schedule_service()

            # If medication exists, update; else create
            med = db.query(models.Medication).filter(
                models.Medication.patient_id == act.patient_id,
                models.Medication.name.ilike(f"%{name}%")
            ).order_by(models.Medication.id.desc()).first()

            if med:
                updated = False
                if not med.dosage and dosage:
                    med.dosage = dosage
                    updated = True
                if not med.frequency and frequency:
                    med.frequency = frequency
                    updated = True
                if updated:
                    db.add(med)
                    db.commit()
                    db.refresh(med)
            else:
                # medication_service.add_medication is async; call and wait
                med_coro = medication_service.add_medication(
                    patient_id=act.patient_id,
                    name=name,
                    dosage=dosage,
                    frequency=frequency,
                    frequency_per_day=len(times) if times else 1,
                    db=db
                )
                if hasattr(med_coro, '__await__'):
                    import asyncio
                    med = asyncio.get_event_loop().run_until_complete(med_coro)
                else:
                    med = med_coro

            # persist recurring times
            med.recurring_times = times
            db.add(med)
            db.commit()
            db.refresh(med)

            # Create schedules for today
            created = []
            from datetime import date
            today = date.today()
            for tstr in times:
                try:
                    hh, mm = [int(x) for x in tstr.split(":")[:2]]
                except Exception:
                    continue
                exists = db.query(models.Schedule).filter(
                    models.Schedule.patient_id == act.patient_id,
                    models.Schedule.medication_id == med.id,
                    models.Schedule.scheduled_date == today,
                    models.Schedule.scheduled_time == tstr
                ).first()
                if exists:
                    created.append(exists.id)
                    continue
                s = models.Schedule(
                    patient_id=act.patient_id,
                    medication_id=med.id,
                    scheduled_date=today,
                    scheduled_time=tstr,
                    medications_list=[med.name],
                    status='pending',
                    notes='Created by liaison background processor'
                )
                db.add(s)
                db.commit()
                db.refresh(s)
                created.append(s.id)

            act.output_data = {'medication_id': med.id, 'schedule_ids': created}
            act.is_successful = True
            db.add(act)
            db.commit()
            return True
    except Exception:
        return False



async def _try_handle_medication_add(
    message: str,
    patient_id: int,
    db: Session,
    conversation_history: Optional[List[ChatMessage]] = None
) -> Optional[ChatResponse]:
    """Lightweight intent handler: add medication when structured input is provided."""
    lower = message.lower().strip()

    name_match = re.search(r"name\s*[:=]\s*([^,;\n]+)", message, re.IGNORECASE)
    dosage_match = re.search(r"dosage\s*[:=]\s*([^,;\n]+)", message, re.IGNORECASE)
    freq_match = re.search(r"frequency\s*[:=]\s*([^,;\n]+)", message, re.IGNORECASE)

    heuristic = _parse_unlabeled_med_line(message) if not (name_match and dosage_match and freq_match) else None

    # Determine whether this message should be treated as an add:
    # - explicit 'add medication' phrasing, OR
    # - the user is replying to the assistant's direct request for name/dosage/frequency, OR
    # - the message looks like an unlabeled med line that we can parse heuristically
    prefix_present = any(prefix in lower for prefix in ["add med", "add medication", "please add medication"])
    asked_for_details = False
    if conversation_history:
        # look back a few messages to see if assistant asked for details
        for msg in reversed(conversation_history[-4:]):
            if msg.role == "assistant":
                txt = msg.content.lower()
                if any(phrase in txt for phrase in ["i need the name", "i need name", "please tell me the name", "can you please tell me the name", "i need name, dosage, and frequency", "please tell me the name of the medication"]):
                    asked_for_details = True
                    break

    looks_like_med_line = bool(heuristic)

    if not (prefix_present or asked_for_details or looks_like_med_line):
        return None

    # If user is only confirming (e.g., 'Yes it is correct') and we have a queued AgentActivity, apply it
    confirmation_match = re.match(r"^\s*(yes|yep|yeah|correct|that's correct|that is correct|confirm|confirmed|ok|okay)\b", message.strip().lower())
    if confirmation_match and asked_for_details:
        # Try to find a recent queued add_medication activity for this patient
        recent = db.query(models.AgentActivity).filter(
            models.AgentActivity.patient_id == patient_id,
            models.AgentActivity.action == 'add_medication',
            models.AgentActivity.is_successful == False
        ).order_by(models.AgentActivity.timestamp.desc()).first()

        if recent:
            # Use the same background processor to perform the add synchronously and then report back
            try:
                await _process_add_med_activity(recent.id)
                # reload activity row
                db.refresh(recent)
                out = recent.output_data or {}
                med_id = out.get('medication_id')
                sched_ids = out.get('schedule_ids', [])
                med_name = None
                if med_id:
                    med_row = db.query(models.Medication).filter(models.Medication.id == med_id).first()
                    med_name = med_row.name if med_row else None

                return ChatResponse(
                    patient_id=patient_id,
                    response=(f"Added {med_name or 'the medication'} (id={med_id}) with {len(sched_ids)} schedule(s)." if recent.is_successful else "I couldn't add that medication right now; I've left the request queued for review."),
                    agent_used="liaison",
                    actions_taken=[{"type": "agent_activity", "activity_id": recent.id}],
                    suggestions=None if recent.is_successful else ["Try again or add the medication from the medications page."],
                    timestamp=datetime.utcnow().isoformat()
                )
            except Exception:
                # If processing failed, fall through to normal flow and ask for clarification
                pass

    # If we don't have labeled fields or heuristic parse, but the user was replying to an assistant prompt,
    # attempt a relaxed, comma-separated fallback parse (e.g., 'Paracetamol, 10 mg, twice daily at 14:30 and 23:00')
    fallback = None
    if (not (name_match and dosage_match and freq_match) and not heuristic) and asked_for_details:
        parts = [p.strip() for p in re.split(r",|;", message) if p.strip()]
        if parts and len(parts) >= 2:
            # first part likely name, look for dosage anywhere
            possible_name = parts[0]
            dose_m = re.search(r"(\d+\s?(mg|mcg|g|ml|units))", message, re.IGNORECASE)
            freq_m = re.search(r"(once daily|twice daily|three times daily|3x daily|bid|tid|daily|morning|evening|night|bedtime)", message, re.IGNORECASE)
            times = _parse_explicit_times(message)
            if dose_m:
                fallback = {
                    "name": possible_name,
                    "dosage": dose_m.group(1).strip(),
                    "frequency": (freq_m.group(1).strip() if freq_m else ("twice daily" if len(times) >= 2 else "once daily"))
                }

    if not (name_match and dosage_match and freq_match) and not heuristic and not fallback:
        # If assistant asked for details but the user didn't provide all three fields, ask for clarification
        return ChatResponse(
            patient_id=patient_id,
            response=(
                "I need name, dosage, and frequency to add a medication. "
                "Example: Add medication name: Metformin, dosage: 500mg, frequency: twice daily."
            ),
            agent_used="liaison",
            actions_taken=[],
            suggestions=["Include all three fields (name, dosage, frequency) in one message."],
            timestamp=datetime.utcnow().isoformat()
        )

    # If we obtained a fallback parse from the user's reply to assistant, adopt it
    if fallback:
        name = fallback.get('name')
        dosage = fallback.get('dosage')
        frequency = fallback.get('frequency')

    medication_service = services.get_medication_service()
    patient_service = services.get_patient_service()

    patient = await patient_service.get_patient(patient_id, db=db)
    if not patient:
        return ChatResponse(
            patient_id=patient_id,
            response="I could not find your profile to add that medication.",
            agent_used="liaison",
            actions_taken=[],
            suggestions=["Please log in again and retry."],
            timestamp=datetime.utcnow().isoformat()
        )

    if fallback:
        name = fallback.get('name')
        dosage = fallback.get('dosage')
        frequency = fallback.get('frequency')
    else:
        name = (name_match.group(1).strip() if name_match else (heuristic or {}).get("name", "")).strip()
        dosage = (dosage_match.group(1).strip() if dosage_match else (heuristic or {}).get("dosage", "")).strip()
        frequency = (freq_match.group(1).strip() if freq_match else (heuristic or {}).get("frequency", "")).strip()

    tz = ZoneInfo(patient.timezone) if patient and patient.timezone else ZoneInfo("UTC")
    today = datetime.now(tz).date()

    try:
        # Create an AgentActivity record for audit/tracing
        activity = models.AgentActivity(
            patient_id=patient_id,
            agent_name="liaison",
            agent_type=models.AgentType.LIAISON,
            action="add_medication",
            activity_type="liaison",
            input_data={"name": name, "dosage": dosage, "frequency": frequency, "source_message": message},
            output_data=None,
            details=None,
            is_successful=False
        )
        db.add(activity)
        db.commit()
        db.refresh(activity)

        # By default, apply immediately when the user provided full structured details
        # (labeled fields or a parsable unlabeled med line). Otherwise, queue for review
        # and only apply synchronously on explicit request or confirmation.
        explicit_apply = (
            any(tok in message.lower() for tok in ["apply now", "add now", "apply", "do it now", "yes add", "confirm add", "confirm"]) or
            asked_for_details or
            ((name_match and dosage_match and freq_match) or looks_like_med_line or fallback)
        )

        # Parse explicit times from the message; if none, infer sensible times
        explicit_times = _parse_explicit_times(message)
        times_to_use = []
        if explicit_times and len(explicit_times) > 0:
            times_to_use = [t.strftime("%H:%M") for t in explicit_times]
        else:
            inferred = _infer_times_from_frequency(frequency, patient)
            times_to_use = [t.strftime("%H:%M") for t in inferred]

        if not explicit_apply:
            # Update activity to indicate it was queued and return a queued response
            activity.output_data = {"queued": True, "suggested_times": times_to_use}
            activity.is_successful = False
            db.add(activity)
            db.commit()
            # Kick off background processing for queued add_medication activities
            try:
                asyncio.create_task(_process_add_med_activity(activity.id))
            except Exception:
                # Non-fatal; activity remains queued for manual/worker processing
                pass

            return ChatResponse(
                patient_id=patient_id,
                response=(
                    f"I've queued the request to add {name} ({dosage}) for review. "
                    "If you'd like me to add it now, reply 'Apply now' or 'Add now'."
                ),
                agent_used="liaison",
                actions_taken=[{"type": "agent_activity", "activity_id": activity.id}],
                suggestions=["Reply 'Apply now' to add immediately, or review in Medications page."],
                timestamp=datetime.utcnow().isoformat()
            )

        # If user explicitly asked to apply now, proceed synchronously (existing behavior)
        schedule_service = services.get_schedule_service()

        # Check for existing medication to avoid duplicates (case-insensitive)
        existing_med = db.query(models.Medication).filter(
            models.Medication.patient_id == patient_id,
            models.Medication.name.ilike(f"%{name}%")
        ).order_by(models.Medication.id.desc()).first()

        if existing_med:
            med = existing_med
            # update dosage/frequency if missing
            updated = False
            if not med.dosage and dosage:
                med.dosage = dosage
                updated = True
            if not med.frequency and frequency:
                med.frequency = frequency
                updated = True
            if updated:
                db.add(med)
                db.commit()
                db.refresh(med)
        else:
            # Add medication via service (synchronous await)
            med = await medication_service.add_medication(
                patient_id=patient_id,
                name=name,
                dosage=dosage,
                frequency=frequency,
                frequency_per_day=len(times_to_use) if times_to_use else 1,
                db=db
            )

        # Persist recurring times on medication
        med.recurring_times = times_to_use
        db.add(med)
        db.commit()
        db.refresh(med)

        # Create schedule entries for today for each provided/inferred time
        created_schedule_ids = []
        from datetime import date
        today = date.today()
        for tstr in times_to_use:
            try:
                hh, mm = [int(x) for x in tstr.split(":")[:2]]
                from datetime import time as dtime
                t_obj = dtime(hh, mm)
            except Exception:
                continue

            # Use schedule service to create schedule
            try:
                sched = await schedule_service.create_schedule(
                    patient_id=patient_id,
                    medication_id=med.id,
                    scheduled_time=t_obj,
                    db=db
                )
                created_schedule_ids.append(sched.id)
            except Exception:
                # fallback: create raw Schedule row
                s = models.Schedule(
                    patient_id=patient_id,
                    medication_id=med.id,
                    scheduled_date=today,
                    scheduled_time=tstr,
                    medications_list=[med.name],
                    status="pending"
                )
                db.add(s)
                db.commit()
                db.refresh(s)
                created_schedule_ids.append(s.id)

        # Update activity with output and mark successful
        activity.output_data = {"medication_id": med.id, "schedule_ids": created_schedule_ids}
        activity.is_successful = True
        db.add(activity)
        db.commit()

        return ChatResponse(
            patient_id=patient_id,
            response=(
                f"Added {med.name} {med.dosage} (id={med.id}) with {len(created_schedule_ids)} schedule(s)."
            ),
            agent_used="liaison",
            actions_taken=[{"type": "medication_added", "medication_id": med.id, "schedule_ids": created_schedule_ids}],
            suggestions=None,
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        # If synchronous processing failed, ensure activity records the error and return helpful message
        try:
            activity.is_successful = False
            activity.error_message = str(e)
            db.add(activity)
            db.commit()
        except Exception:
            pass

        return ChatResponse(
            patient_id=patient_id,
            response=f"I could not add the medication right now: {str(e)}. I've queued the request for the liaison agent to review.",
            agent_used="liaison",
            actions_taken=[{"type": "agent_activity", "activity_id": activity.id}],
            suggestions=["Try again or add the medication from the medications page."],
            timestamp=datetime.utcnow().isoformat()
        )


async def _try_handle_missed_or_skipped(
    message: str,
    patient_id: int,
    db: Session
) -> Optional[ChatResponse]:
    """Handle user reports of missed/skipped doses like 'I missed Lisinopril at 12:30' or 'I skipped Metformin'.

    This function will attempt deterministic matching to a scheduled dose and log the event
    via the adherence service, returning a ChatResponse. If ambiguous, it will ask for clarification.
    """
    lower = message.lower().strip()
    if not any(k in lower for k in ["miss", "missed", "skipp", "skipped"]):
        return None

    # Check for a recent clarify activity where we asked which candidate the user meant
    try:
        clar = db.query(models.AgentActivity).filter(
            models.AgentActivity.patient_id == patient_id,
            models.AgentActivity.action == 'clarify_schedule_candidates',
            models.AgentActivity.is_successful == False
        ).order_by(models.AgentActivity.timestamp.desc()).first()
        if clar and clar.output_data and isinstance(clar.output_data, dict):
            candidates = clar.output_data.get('candidates') or []
            # Try to match by index (user replied with '1'/'2'), time, or medication name
            sel = None
            num_m = re.match(r"^\s*(\d+)\s*$", message.strip())
            if num_m:
                idx = int(num_m.group(1)) - 1
                if 0 <= idx < len(candidates):
                    sel = candidates[idx]
            # time match
            if not sel:
                tmatch = re.search(r"(\d{1,2}:\d{2})", message)
                if tmatch:
                    tstr = tmatch.group(1)
                    for c in candidates:
                        if tstr in c.get('display',''):
                            sel = c
                            break
            # name match
            if not sel:
                for c in candidates:
                    namepart = c.get('display','').split(' at ')[0].lower()
                    if namepart and namepart in message.lower():
                        sel = c
                        break

            if sel:
                # load schedule row and proceed as if matched
                sched_id = sel.get('schedule_id')
                schedule_row = db.query(models.Schedule).filter(models.Schedule.id == sched_id).first()
                # mark clarify activity successful (resolved)
                try:
                    clar.is_successful = True
                    clar.output_data['selected'] = sel
                    db.add(clar)
                    db.commit()
                except Exception:
                    pass
            else:
                schedule_row = None
    except Exception:
        schedule_row = None

    # Extract times and medication name heuristically
    times = _parse_explicit_times(message)

    name = None
    m = re.search(r"(?:missed|miss|skipped|skip)\s+([A-Za-z0-9\-\s]+?)(?:\s+at|\s+\d|$)", message, re.IGNORECASE)
    if m:
        name = m.group(1).strip()

    medication_service = services.get_medication_service()
    adherence_service = services.get_adherence_service()

    med = None
    if name:
        med = db.query(models.Medication).filter(
            models.Medication.patient_id == patient_id,
            models.Medication.name.ilike(f"%{name}%")
        ).order_by(models.Medication.name).first()

    # Determine timezone
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    try:
        tz = ZoneInfo(patient.timezone) if patient and patient.timezone else ZoneInfo('UTC')
    except Exception:
        tz = ZoneInfo('UTC')

    # If the user provided an explicit time, construct a taken_at datetime in patient's local tz
    taken_at = None
    parsed_time = None
    taken_local = None
    if times and len(times) > 0:
        parsed_time = times[0]  # use first explicit time
        # Build a datetime in patient local tz using today's date in that tz
        now_local = datetime.now(tz)
        taken_local = now_local.replace(hour=parsed_time.hour, minute=parsed_time.minute, second=0, microsecond=0)
        # Convert to naive UTC (adherence service expects naive utc datetimes)
        try:
            taken_utc = taken_local.astimezone(ZoneInfo('UTC'))
            taken_at = taken_utc.replace(tzinfo=None)
        except Exception:
            taken_at = datetime.utcnow()

    # Find schedule candidate similar to how taken reports do
    schedule_row = None
    if med:
        q = db.query(models.Schedule).filter(
            models.Schedule.patient_id == patient_id,
            models.Schedule.medication_id == med.id,
            models.Schedule.status == 'pending'
        )
        if taken_at and parsed_time:
            local_date = taken_local.date() if taken_local else taken_at.date()
            time_str = parsed_time.strftime('%H:%M')
            schedule_row = q.filter(
                models.Schedule.scheduled_date == local_date,
                models.Schedule.scheduled_time == time_str
            ).order_by(models.Schedule.scheduled_date, models.Schedule.scheduled_time).first()
        else:
            # Do not auto-select when no explicit time; let proximity logic handle it
            schedule_row = None
    else:
        q = db.query(models.Schedule).filter(
            models.Schedule.patient_id == patient_id,
            models.Schedule.status == 'pending'
        )
        if taken_at and parsed_time:
            local_date = taken_local.date() if taken_local else taken_at.date()
            time_str = parsed_time.strftime('%H:%M')
            schedule_row = q.filter(
                models.Schedule.scheduled_date == local_date,
                models.Schedule.scheduled_time == time_str
            ).order_by(models.Schedule.scheduled_date, models.Schedule.scheduled_time).first()
        else:
            schedule_row = None

    # If no explicit match, try the ±2 hour proximity window
    if not schedule_row and not parsed_time:
        now_local = datetime.now(tz)
        window_start = now_local - timedelta(hours=2)
        window_end = now_local + timedelta(hours=2)

        candidates = []
        q = db.query(models.Schedule).filter(
            models.Schedule.patient_id == patient_id,
            models.Schedule.status == 'pending'
        )
        rows = q.filter(models.Schedule.scheduled_date.in_([
            window_start.date(), now_local.date(), window_end.date()
        ])).order_by(models.Schedule.scheduled_date, models.Schedule.scheduled_time).all()

        for u in rows:
            try:
                sched_date = u.scheduled_date if isinstance(u.scheduled_date, date) else datetime.strptime(str(u.scheduled_date), "%Y-%m-%d").date()
                sched_time_str = u.scheduled_time if isinstance(u.scheduled_time, str) else str(u.scheduled_time)
                hour_min = [int(x) for x in sched_time_str.split(":")[:2]]
                sched_dt = datetime.combine(sched_date, time(hour_min[0], hour_min[1]))
                sched_dt = sched_dt.replace(tzinfo=tz)
            except Exception:
                continue

            if window_start <= sched_dt <= window_end:
                # If the user included a medication name, filter to matching med names
                if med:
                    if u.medication_id == med.id:
                        candidates.append((u, sched_dt))
                else:
                    candidates.append((u, sched_dt))

        if not candidates:
            return ChatResponse(
                patient_id=patient_id,
                response=(
                    "I couldn't find any scheduled dose within two hours to mark as missed/skipped. "
                    "Please tell me which medication and time you missed, for example: 'I missed Lisinopril at 12:30'."
                ),
                agent_used="monitoring",
                actions_taken=[],
                suggestions=["Specify medication name and time, e.g., 'I missed Lisinopril at 12:30'"],
                timestamp=datetime.utcnow().isoformat()
            )

        if len(candidates) == 1:
            schedule_row, sched_dt = candidates[0]
        else:
            options_lines = []
            for u, sched_dt in candidates:
                med_name = (u.medications_list or [u.medication.name if u.medication else 'Unknown'])[0]
                options_lines.append(f"- {med_name} at {sched_dt.astimezone(tz).strftime('%Y-%m-%d %H:%M')}")

            content = (
                "I found multiple scheduled doses within two hours. Which one did you miss/skip?\n" + "\n".join(options_lines) +
                "\nPlease reply with the medication name or the scheduled time (e.g., 'I missed Lisinopril at 12:30')."
            )
            # Create a clarify AgentActivity so that the user's follow-up can reference candidates
            try:
                candidate_list = []
                for u, sched_dt in candidates:
                    display = f"{(u.medications_list or [u.medication.name if u.medication else 'Unknown'])[0]} at {sched_dt.astimezone(tz).strftime('%Y-%m-%d %H:%M')}"
                    candidate_list.append({"schedule_id": u.id, "display": display})

                clar_act = models.AgentActivity(
                    patient_id=patient_id,
                    agent_name="monitoring",
                    agent_type=models.AgentType.MONITORING,
                    action="clarify_schedule_candidates",
                    activity_type="clarify",
                    input_data={"prompt": content},
                    output_data={"candidates": candidate_list},
                    is_successful=False
                )
                db.add(clar_act)
                db.commit()
                db.refresh(clar_act)
                act_info = {"type": "clarify_candidates", "activity_id": clar_act.id}
            except Exception:
                act_info = None

            return ChatResponse(
                patient_id=patient_id,
                response=content,
                agent_used="monitoring",
                actions_taken=[act_info] if act_info else [],
                suggestions=[(u.medications_list or [u.medication.name if u.medication else 'Unknown'])[0] for u, _ in candidates],
                timestamp=datetime.utcnow().isoformat()
            )

    if not schedule_row:
        return ChatResponse(
            patient_id=patient_id,
            response="I couldn't find a matching scheduled dose to mark as missed/skipped. Can you tell me the medication name and the scheduled time?",
            agent_used="monitoring",
            actions_taken=[],
            suggestions=["Please specify medication name and time, e.g., 'I missed Metformin at 12:00'"],
            timestamp=datetime.utcnow().isoformat()
        )


async def _try_handle_medication_update(
    message: str,
    patient_id: int,
    db: Session,
    conversation_history: Optional[List[ChatMessage]] = None
) -> Optional[ChatResponse]:
    """Handle direct medication update requests deterministically.

    Examples:
      - "Reduce my dosage from 10mg to 5mg of my Montelukast"
      - "Change Montelukast dosage to 5mg"
    """
    lower = message.lower()
    if not any(k in lower for k in ["change", "update", "reduce", "set", "change dosage", "dosage to", "dosage:"]):
        return None

    # Extract medication name heuristically
    name = None
    m = re.search(r"(?:of my|of|for|my)?\s*([A-Za-z0-9\'\-\s]+?)\s*(?:dosage|to|from|\(|medication|$)", message, re.IGNORECASE)
    if m:
        candidate = m.group(1).strip()
        # guard against capturing generic phrases like 'i want'
        if len(candidate.split()) <= 6 and not candidate.lower().startswith('i '):
            name = candidate

    # Extract new dosage like '5mg'
    dose_m = re.search(r"(\d+\s?(mg|mcg|g|ml|units))", message, re.IGNORECASE)
    new_dosage = dose_m.group(1).strip() if dose_m else None

    # If not enough info, ask for clarification
    if not name or not new_dosage:
        return ChatResponse(
            patient_id=patient_id,
            response=(
                "I need the medication name and the new dosage to update. "
                "Example: 'Change Montelukast dosage to 5mg.'"
            ),
            agent_used="liaison",
            actions_taken=[],
            suggestions=["Provide medication name and new dosage, e.g., 'Montelukast 5mg'"],
            timestamp=datetime.utcnow().isoformat()
        )

    # If we still don't have a clear name, try to match any active medication names
    med = None
    if name:
        med = db.query(models.Medication).filter(
            models.Medication.patient_id == patient_id,
            models.Medication.name.ilike(f"%{name}%")
        ).order_by(models.Medication.id.desc()).first()

    if not med:
        # Try direct substring match against active meds for this patient
        meds = db.query(models.Medication).filter(
            models.Medication.patient_id == patient_id,
            models.Medication.active == True
        ).all()
        lowered = message.lower()
        for mrow in meds:
            if mrow.name and mrow.name.lower() in lowered:
                med = mrow
                break

    if not med and conversation_history:
        # Look back in conversation for the most recent mention of a medication name
        for msg in reversed(conversation_history):
            # consider both user and assistant messages
            txt = msg.content.lower()
            for mrow in db.query(models.Medication).filter(models.Medication.patient_id == patient_id).all():
                if mrow.name and mrow.name.lower() in txt:
                    med = mrow
                    break
            if med:
                break

    if not med:
        return ChatResponse(
            patient_id=patient_id,
            response=(f"I couldn't find a medication matching '{name or 'the name you provided'}'. "
                      "Please check the name and try again or mention which medication you mean."),
            agent_used="liaison",
            actions_taken=[],
            suggestions=["Check medication spelling or view your medications list."],
            timestamp=datetime.utcnow().isoformat()
        )

    # Update medication record (record-only; do not give clinical advice)
    medication_service = services.get_medication_service()
    try:
        updates = {"dosage": new_dosage}
        updated = await medication_service.update_medication(med.id, updates, db=db)

        # Create an AgentActivity for traceability
        activity = models.AgentActivity(
            patient_id=patient_id,
            agent_name="liaison",
            agent_type=models.AgentType.LIAISON,
            action="update_medication",
            activity_type="liaison",
            input_data={"medication_id": med.id, "updates": updates, "source_message": message},
            output_data={"medication_id": med.id, "updated_fields": list(updates.keys())},
            is_successful=True
        )
        db.add(activity)
        db.commit()
        db.refresh(activity)

        return ChatResponse(
            patient_id=patient_id,
            response=(
                f"Updated {med.name} (id={med.id}): dosage set to {new_dosage}. "
                "I cannot provide medical dosing advice — please confirm this change with your clinician or pharmacist."
            ),
            agent_used="liaison",
            actions_taken=[{"type": "medication_updated", "medication_id": med.id, "updates": updates, "activity_id": activity.id}],
            suggestions=["Contact your clinician or pharmacist before making medication changes."],
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        return ChatResponse(
            patient_id=patient_id,
            response=f"I couldn't update the medication due to an error: {str(e)}",
            agent_used="liaison",
            actions_taken=[],
            suggestions=["Try again or update the medication from the medications page."],
            timestamp=datetime.utcnow().isoformat()
        )

    # Log the missed or skipped dose
    try:
        if "skip" in lower or "skipp" in lower:
            log = await adherence_service.log_dose_skipped(
                patient_id=patient_id,
                schedule_id=schedule_row.id,
                medication_id=schedule_row.medication_id,
                reason=None,
                db=db
            )
            verb = "marked as skipped"
        else:
            log = await adherence_service.log_dose_missed(
                patient_id=patient_id,
                schedule_id=schedule_row.id,
                medication_id=schedule_row.medication_id,
                reason=None,
                db=db
            )
            verb = "marked as missed"

        sched_display = f"{schedule_row.scheduled_date} {schedule_row.scheduled_time}"
        return ChatResponse(
            patient_id=patient_id,
            response=f"Logged { (schedule_row.medications_list or [schedule_row.medication.name if schedule_row.medication else 'medication'])[0] } as {verb} for {sched_display}.",
            agent_used="monitoring",
            actions_taken=[{"type": "log_missed" if "miss" in lower else "log_skipped", "log_id": log.id, "schedule_id": schedule_row.id}],
            suggestions=None,
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        return ChatResponse(
            patient_id=patient_id,
            response=f"I tried to mark that dose but encountered an error: {str(e)}",
            agent_used="monitoring",
            actions_taken=[],
            suggestions=["Try again or mark the dose from the schedule page."],
            timestamp=datetime.utcnow().isoformat()
        )


async def _try_handle_adherence_query(
    message: str,
    patient_id: int,
    db: Session
) -> Optional[ChatResponse]:
    """Handle explicit adherence/statistics queries deterministically and return numeric stats."""
    lower = message.lower()
    if not any(kw in lower for kw in ["adherence", "adherence rate", "adherence stats", "my adherence", "adherence %", "adherence%"]):
        return None

    # parse optional days window e.g., 'last 14 days'
    days = 7
    m = re.search(r"(\d+)\s+days", message.lower())
    if m:
        try:
            days = int(m.group(1))
        except Exception:
            days = 7

    adherence_service = services.get_adherence_service()
    try:
        rate = await adherence_service.get_adherence_rate(patient_id, days=days, db=db)
        # Return a concise numeric JSON-like string to ensure numbers are prominent
        payload = {
            "adherence_rate": rate.get("adherence_rate", 0.0),
            "total_doses": rate.get("total_doses", 0),
            "taken": rate.get("taken", 0),
            "missed": rate.get("missed", 0),
            "skipped": rate.get("skipped", 0),
            "delayed": rate.get("delayed", 0),
            "days_analyzed": rate.get("days_analyzed", days)
        }
        return ChatResponse(
            patient_id=patient_id,
            response=json.dumps(payload),
            agent_used="monitoring",
            actions_taken=None,
            suggestions=None,
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        return ChatResponse(
            patient_id=patient_id,
            response=f"Could not compute adherence stats: {str(e)}",
            agent_used="monitoring",
            actions_taken=None,
            suggestions=["Try again later"],
            timestamp=datetime.utcnow().isoformat()
        )


async def _try_handle_report_taken(
    message: str,
    patient_id: int,
    db: Session
) -> Optional[ChatResponse]:
    """Handle direct user reports like 'Report Lisinopril 22:00 taken' or 'I took Metformin at 20:00'.

    This is a deterministic handler that logs adherence without calling the LLM when possible.
    """
    lower = message.lower().strip()
    # Only handle explicit 'took' / 'taken' / 'mark ... taken' reports or quick action labels
    quick_labels = ["i took my medication", "i took my meds", "i took my medication"]
    if not (
        "took" in lower
        or "taken" in lower
        or "i took" in lower
        or ("report" in lower and "taken" in lower)
        or ("mark" in lower and ("taken" in lower or re.search(r"\d{1,2}:\d{2}", message)))
        or ("log" in lower and "taken" in lower)
        or lower.strip() in quick_labels
    ):
        return None

    # Extract times (explicit) and medication name heuristically
    times = _parse_explicit_times(message)

    # Check for a recent clarify activity (user is replying to a multiple-choice question)
    try:
        clar = db.query(models.AgentActivity).filter(
            models.AgentActivity.patient_id == patient_id,
            models.AgentActivity.action == 'clarify_schedule_candidates',
            models.AgentActivity.is_successful == False
        ).order_by(models.AgentActivity.timestamp.desc()).first()
        if clar and clar.output_data and isinstance(clar.output_data, dict):
            candidates = clar.output_data.get('candidates') or []
            sel = None
            num_m = re.match(r"^\s*(\d+)\s*$", message.strip())
            if num_m:
                idx = int(num_m.group(1)) - 1
                if 0 <= idx < len(candidates):
                    sel = candidates[idx]
            if not sel:
                tmatch = re.search(r"(\d{1,2}:\d{2})", message)
                if tmatch:
                    tstr = tmatch.group(1)
                    for c in candidates:
                        if tstr in c.get('display',''):
                            sel = c
                            break
            if not sel:
                for c in candidates:
                    namepart = c.get('display','').split(' at ')[0].lower()
                    if namepart and namepart in message.lower():
                        sel = c
                        break

            if sel:
                sched_id = sel.get('schedule_id')
                schedule_row = db.query(models.Schedule).filter(models.Schedule.id == sched_id).first()
                # mark clarify activity resolved
                try:
                    clar.is_successful = True
                    clar.output_data['selected'] = sel
                    db.add(clar)
                    db.commit()
                except Exception:
                    pass
            else:
                schedule_row = None
    except Exception:
        schedule_row = None

    # Heuristic medication name extraction: look for 'took <name>' or 'report <name>' patterns
    name = None
    m = re.search(r"took\s+([A-Za-z0-9\-\s]+?)(?:\s+at|\s+\d|$)", message, re.IGNORECASE)
    if m:
        name = m.group(1).strip()
    else:
        m2 = re.search(r"report\s+([A-Za-z0-9\-\s]+?)\s+(?:taken|at|\d)", message, re.IGNORECASE)
        if m2:
            name = m2.group(1).strip()

    # Services
    medication_service = services.get_medication_service()
    adherence_service = services.get_adherence_service()

    # Resolve medication by name if provided
    med = None
    if name:
        med = db.query(models.Medication).filter(
            models.Medication.patient_id == patient_id,
            models.Medication.name.ilike(f"%{name}%")
        ).order_by(models.Medication.name).first()

    # Determine patient timezone for interpreting reported time
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    try:
        tz = ZoneInfo(patient.timezone) if patient and patient.timezone else ZoneInfo('UTC')
    except Exception:
        tz = ZoneInfo('UTC')

    # If the user provided an explicit time, construct a taken_at datetime in patient's local tz
    taken_at = None
    parsed_time = None
    taken_local = None
    if times and len(times) > 0:
        parsed_time = times[0]  # use first explicit time
        # Build a datetime in patient local tz using today's date in that tz
        now_local = datetime.now(tz)
        taken_local = now_local.replace(hour=parsed_time.hour, minute=parsed_time.minute, second=0, microsecond=0)
        # Convert to naive UTC (adherence service expects naive utc datetimes)
        try:
            taken_utc = taken_local.astimezone(ZoneInfo('UTC'))
            taken_at = taken_utc.replace(tzinfo=None)
        except Exception:
            taken_at = datetime.utcnow()

    # Find a matching schedule row. Prefer exact date+time match for the reported time, else fall back to next pending.
    schedule_row = None
    if med:
        # Look for a schedule for that medication matching the reported time (if any) or next pending
        q = db.query(models.Schedule).filter(
            models.Schedule.patient_id == patient_id,
            models.Schedule.medication_id == med.id,
            models.Schedule.status == 'pending'
        )
        if taken_at and parsed_time:
            # Use the patient's local date for matching schedules (taken_local),
            # because schedules are stored with patient-local dates.
            local_date = taken_local.date() if taken_local else taken_at.date()
            time_str = parsed_time.strftime('%H:%M')
            # Try exact match first
            schedule_row = q.filter(
                models.Schedule.scheduled_date == local_date,
                models.Schedule.scheduled_time == time_str
            ).order_by(models.Schedule.scheduled_date, models.Schedule.scheduled_time).first()
            if not schedule_row:
                # Fallback to any pending for that med
                schedule_row = q.order_by(models.Schedule.scheduled_date, models.Schedule.scheduled_time).first()
        else:
            # Do not auto-select the oldest pending schedule when no medication or explicit time
            # was provided. Leave schedule_row as None so we can attempt a proximity-based
            # inference (±2 hours) below. This prevents incorrectly logging an unrelated
            # old pending dose when the user used a generic quick action like
            # 'I took my medication'.
            schedule_row = None
    else:
        # No medication identified; try to match any pending schedule at the reported time
        q = db.query(models.Schedule).filter(
            models.Schedule.patient_id == patient_id,
            models.Schedule.status == 'pending'
        )
        if taken_at and parsed_time:
            local_date = taken_local.date() if taken_local else taken_at.date()
            time_str = parsed_time.strftime('%H:%M')
            schedule_row = q.filter(
                models.Schedule.scheduled_date == local_date,
                models.Schedule.scheduled_time == time_str
            ).order_by(models.Schedule.scheduled_date, models.Schedule.scheduled_time).first()
            if not schedule_row:
                # If no exact match, pick the next pending
                # Only fallback to next pending when the user provided an explicit time but no exact match
                schedule_row = q.order_by(models.Schedule.scheduled_date, models.Schedule.scheduled_time).first()
        else:
            # Do NOT auto-select the oldest pending schedule when the user did not provide
            # an explicit time or medication. Let the proximity-based inference (±2 hours)
            # handle generic quick actions like 'I took my medication'. This avoids
            # mistakenly logging an unrelated older dose.
            schedule_row = None

    # If there was no explicit schedule match and no explicit time/medication provided,
    # try to infer which scheduled dose the user likely meant based on time proximity
    if not schedule_row and not parsed_time and not med:
        # look for pending schedules within +/-2 hours of now in patient's local tz
        now_local = datetime.now(tz)
        window_start = now_local - timedelta(hours=2)
        window_end = now_local + timedelta(hours=2)

        candidates = []
        q = db.query(models.Schedule).filter(
            models.Schedule.patient_id == patient_id,
            models.Schedule.status == 'pending'
        )
        # Consider schedules for yesterday, today, and tomorrow to capture boundary cases
        rows = q.filter(models.Schedule.scheduled_date.in_([
            window_start.date(), now_local.date(), window_end.date()
        ])).order_by(models.Schedule.scheduled_date, models.Schedule.scheduled_time).all()

        for u in rows:
            try:
                sched_date = u.scheduled_date if isinstance(u.scheduled_date, date) else datetime.strptime(str(u.scheduled_date), "%Y-%m-%d").date()
                sched_time_str = u.scheduled_time if isinstance(u.scheduled_time, str) else str(u.scheduled_time)
                hour_min = [int(x) for x in sched_time_str.split(":")[:2]]
                sched_dt = datetime.combine(sched_date, time(hour_min[0], hour_min[1]))
                sched_dt = sched_dt.replace(tzinfo=tz)
            except Exception:
                continue

            if window_start <= sched_dt <= window_end:
                candidates.append((u, sched_dt))

        if not candidates:
            return ChatResponse(
                patient_id=patient_id,
                response=(
                    "I couldn't find any scheduled dose within two hours of now to mark. "
                    "I can only mark doses that have a scheduled time. Please tell me the medication name and time, "
                    "for example: 'I took Metformin at 20:00', or use the medication page to mark a specific dose."
                ),
                agent_used="monitoring",
                actions_taken=[],
                suggestions=["Please specify medication name and time, e.g., 'I took Metformin at 20:00'"],
                timestamp=datetime.utcnow().isoformat()
            )

        if len(candidates) == 1:
            schedule_row, sched_dt = candidates[0]
            # Use current local time as reported time
            taken_local = now_local.replace(second=0, microsecond=0)
            try:
                taken_utc = taken_local.astimezone(ZoneInfo('UTC'))
                taken_at = taken_utc.replace(tzinfo=None)
            except Exception:
                taken_at = datetime.utcnow()
        else:
            # Multiple possible meds — ask the user to clarify which medication they took
            options_lines = []
            for u, sched_dt in candidates:
                med_name = (u.medications_list or [u.medication.name if u.medication else 'Unknown'])[0]
                options_lines.append(f"- {med_name} at {sched_dt.astimezone(tz).strftime('%Y-%m-%d %H:%M')}")

            content = (
                "I found multiple scheduled doses within two hours. Which one did you take?\n" + "\n".join(options_lines) +
                "\nPlease reply with the medication name or the scheduled time (e.g., 'I took Amlodipine at 21:30')."
            )

            return ChatResponse(
                patient_id=patient_id,
                response=content,
                agent_used="monitoring",
                actions_taken=[],
                suggestions=[(u.medications_list or [u.medication.name if u.medication else 'Unknown'])[0] for u, _ in candidates],
                timestamp=datetime.utcnow().isoformat()
            )

    if not schedule_row:
        return ChatResponse(
            patient_id=patient_id,
            response="I couldn't find a matching scheduled dose to log. Can you tell me the medication name and the scheduled time?",
            agent_used="monitoring",
            actions_taken=[],
            suggestions=["Please specify medication name and time, e.g., 'I took Metformin at 20:00'"],
            timestamp=datetime.utcnow().isoformat()
        )

    # Log the dose as taken
    try:
        log = await adherence_service.log_dose_taken(
            patient_id=patient_id,
            schedule_id=schedule_row.id,
            medication_id=schedule_row.medication_id,
            taken_at=taken_at,
            db=db
        )

        # Show a human-friendly confirmation time: use reported taken_at if provided, else scheduled
        try:
            if taken_at:
                # taken_at is stored as naive UTC in the DB; convert to patient local tz for display
                try:
                    taken_with_tz = taken_at.replace(tzinfo=ZoneInfo('UTC'))
                    confirm_time = taken_with_tz.astimezone(tz).strftime('%Y-%m-%d %H:%M')
                except Exception:
                    confirm_time = taken_at.strftime('%Y-%m-%d %H:%M')
            else:
                # scheduled_date/time are in patient-local terms; display directly
                confirm_time = f"{schedule_row.scheduled_date} {schedule_row.scheduled_time}"
        except Exception:
            confirm_time = f"{schedule_row.scheduled_date} {schedule_row.scheduled_time}"

        return ChatResponse(
            patient_id=patient_id,
            response=f"Logged { (schedule_row.medications_list or [schedule_row.medication.name if schedule_row.medication else 'medication'])[0] } as taken at {confirm_time}.",
            agent_used="monitoring",
            actions_taken=[{"type": "log_dose", "log_id": log.id, "schedule_id": schedule_row.id}],
            suggestions=None,
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        return ChatResponse(
            patient_id=patient_id,
            response=f"I tried to log that dose but encountered an error: {str(e)}",
            agent_used="monitoring",
            actions_taken=[],
            suggestions=["Try again or use the 'I took my medication' quick action."],
            timestamp=datetime.utcnow().isoformat()
        )


async def _try_handle_next_dose(
    message: str,
    patient_id: int,
    db: Session
) -> Optional[ChatResponse]:
    """Deterministic handler for "next dose" queries that reads schedule data directly.
    Returns a ChatResponse if the message matches a next-dose intent; otherwise None.
    """
    lower = message.lower()
    if not any(phrase in lower for phrase in ["next dose", "what's my next dose", "next medication", "next med"]):
        return None

    # Load patient timezone if available
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if not patient:
        return ChatResponse(
            patient_id=patient_id,
            response="I could not find your profile. Please select a patient and try again.",
            agent_used="monitoring",
            actions_taken=[],
            suggestions=["View schedule", "Log adherence", "Contact clinician"],
            timestamp=datetime.utcnow().isoformat()
        )

    try:
        tz = ZoneInfo(patient.timezone) if patient.timezone else ZoneInfo("UTC")
    except Exception:
        tz = ZoneInfo("UTC")

    now = datetime.now(tz)

    # Find the next pending scheduled dose (status 'pending') ordered by date/time
    upcoming = db.query(models.Schedule).filter(
        models.Schedule.patient_id == patient_id,
        models.Schedule.status == 'pending'
    ).order_by(models.Schedule.scheduled_date, models.Schedule.scheduled_time).all()

    # Parse schedule rows into datetimes and pick the first that's >= now
    next_item = None
    for u in upcoming:
        # scheduled_date may be a date, scheduled_time a string like '08:00'
        try:
            sched_date = u.scheduled_date if isinstance(u.scheduled_date, date) else datetime.strptime(str(u.scheduled_date), "%Y-%m-%d").date()
            sched_time_str = u.scheduled_time if isinstance(u.scheduled_time, str) else str(u.scheduled_time)
            hour_min = [int(x) for x in sched_time_str.split(":")[:2]]
            sched_dt = datetime.combine(sched_date, time(hour_min[0], hour_min[1]))
            sched_dt = sched_dt.replace(tzinfo=tz)
        except Exception:
            continue

        if sched_dt >= now:
            next_item = (u, sched_dt)
            break

    if not next_item:
        # If none pending, look for any upcoming (including non-pending)
        fallback = db.query(models.Schedule).filter(
            models.Schedule.patient_id == patient_id
        ).order_by(models.Schedule.scheduled_date, models.Schedule.scheduled_time).first()
        if not fallback:
            return ChatResponse(
                patient_id=patient_id,
                response="I couldn't find any scheduled doses for you.",
                agent_used="monitoring",
                actions_taken=[],
                suggestions=["View schedule", "Log adherence", "Contact clinician"],
                timestamp=datetime.utcnow().isoformat()
            )

        u = fallback
        try:
            sched_date = u.scheduled_date if isinstance(u.scheduled_date, date) else datetime.strptime(str(u.scheduled_date), "%Y-%m-%d").date()
            sched_time_str = u.scheduled_time if isinstance(u.scheduled_time, str) else str(u.scheduled_time)
            hour_min = [int(x) for x in sched_time_str.split(":")[:2]]
            sched_dt = datetime.combine(sched_date, time(hour_min[0], hour_min[1]))
            sched_dt = sched_dt.replace(tzinfo=tz)
        except Exception:
            return ChatResponse(
                patient_id=patient_id,
                response="I found schedule entries but could not parse their times.",
                agent_used="monitoring",
                actions_taken=[],
                suggestions=["View schedule", "Log adherence", "Contact clinician"],
                timestamp=datetime.utcnow().isoformat()
            )

        content = f"Your next scheduled dose is {(u.medications_list or [u.medication.name if u.medication else 'Unknown'])[0]} at {sched_dt.astimezone(tz).strftime('%Y-%m-%d %H:%M')} ({'pending' if u.status == 'pending' else u.status})."

        return ChatResponse(
            patient_id=patient_id,
            response=content,
            agent_used="monitoring",
            actions_taken=[],
            suggestions=["View schedule", "Log adherence", "Contact clinician"],
            timestamp=datetime.utcnow().isoformat()
        )

    u, sched_dt = next_item
    content = f"Your next scheduled dose is {(u.medications_list or [u.medication.name if u.medication else 'Unknown'])[0]} at {sched_dt.astimezone(tz).strftime('%Y-%m-%d %H:%M')} (pending)."

    return ChatResponse(
        patient_id=patient_id,
        response=content,
        agent_used="monitoring",
        actions_taken=[],
        suggestions=["View schedule", "Log adherence", "Contact clinician"],
        timestamp=datetime.utcnow().isoformat()
    )


# ==================== ENDPOINTS ====================

@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Send a message to the AI assistant
    
    The multi-agent system will process the message and route it
    to the appropriate agent (Planning, Monitoring, Barrier, or Liaison)
    """
    llm_service = services.get_llm_service()
    patient_service = services.get_patient_service()
    
    # Get patient context if requested
    context = ""
    if request.include_context:
        patient = await patient_service.get_patient(request.patient_id, db=db)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient {request.patient_id} not found"
            )
        
        summary = await patient_service.get_patient_summary(request.patient_id, db=db)
        # Build richer context: profile, medication list, recent adherence events, upcoming doses
        meds = db.query(models.Medication).filter(
            models.Medication.patient_id == request.patient_id,
            models.Medication.active == True
        ).order_by(models.Medication.name).limit(20).all()

        med_lines = []
        for m in meds:
            med_lines.append(f"- {m.name} ({m.dosage or 'unknown dosage'}) - {m.frequency or 'unspecified'})")

        # Recent adherence logs (sliding window)
        recent_logs = db.query(models.AdherenceLog).filter(
            models.AdherenceLog.patient_id == request.patient_id
        ).order_by(models.AdherenceLog.logged_at.desc()).limit(7).all()

        log_lines = []
        for l in recent_logs:
            time_str = _format_scheduled_time_for_patient(l.scheduled_time, patient.timezone if patient and patient.timezone else 'UTC')
            status_text = l.status.value if hasattr(l.status, 'value') else str(l.status)
            med_name = l.medication.name if getattr(l, 'medication', None) else getattr(l, 'medication_id', 'Unknown')
            log_lines.append(f"- {time_str}: {med_name} -> {status_text}")

        # Upcoming schedule (next 5)
        upcoming = db.query(models.Schedule).filter(
            models.Schedule.patient_id == request.patient_id,
        ).order_by(models.Schedule.scheduled_date, models.Schedule.scheduled_time).limit(5).all()

        upcoming_lines = []
        for u in upcoming:
            upcoming_lines.append(f"- {u.scheduled_date} {u.scheduled_time}: { (u.medications_list or [u.medication.name if u.medication else 'Unknown'])[0]} ({u.status})")

        # Precompute multi-line blocks to avoid backslashes inside f-string expressions
        med_block = '\n'.join(med_lines) if med_lines else ' - None'
        log_block = '\n'.join(log_lines) if log_lines else ' - None'
        upcoming_block = '\n'.join(upcoming_lines) if upcoming_lines else ' - None'

        context = f"""
    Patient: {patient.full_name}
    Timezone: {patient.timezone}
    Conditions: {', '.join(patient.conditions or [])}
    Active Medications ({len(med_lines)}):
    {med_block}
    Recent Adherence (last {len(log_lines)}):
    {log_block}
    Upcoming (next {len(upcoming_lines)} items):
    {upcoming_block}
    Recent Adherence Rate: {summary.get('recent_adherence_rate', 'N/A')}%
    """

    quick_response = await _try_handle_medication_add(request.message, request.patient_id, db, request.conversation_history)
    if quick_response:
        return quick_response
    # Deterministic handler for updating medications (e.g., "reduce my dosage from 10mg to 5mg of Montelukast")
    update_response = await _try_handle_medication_update(request.message, request.patient_id, db, request.conversation_history)
    if update_response:
        return update_response
    # Deterministic handler for missed/skipped reports (e.g., 'I missed...', 'I skipped...')
    missed_response = await _try_handle_missed_or_skipped(request.message, request.patient_id, db)
    if missed_response:
        return missed_response

    # Deterministic handler for adherence/statistics queries
    adherence_response = await _try_handle_adherence_query(request.message, request.patient_id, db)
    if adherence_response:
        return adherence_response

    # Deterministic handler for "I took X" free-text reports
    report_response = await _try_handle_report_taken(request.message, request.patient_id, db)
    if report_response:
        return report_response

    # Fast-path: answer "next dose" deterministically from schedule data (avoid LLM hallucination)
    next_response = await _try_handle_next_dose(request.message, request.patient_id, db)
    if next_response:
        return next_response
    
    # Build conversation for LLM
    # If the user is asking a general medication question (not about a specific patient),
    # provide a different system prompt and do NOT include patient context.
    generic_med = _is_generic_med_query(request.message)

    default_system_prompt = """You are AdherenceGuardian, an AI assistant helping patients with medication adherence.
You must follow these instructions strictly:

1) Use ONLY the patient context and data provided to you in the system message when answering patient-specific questions. Do NOT invent medications, doses, dates, or adherence events.
2) For structured tasks (schedules, adherence summaries, replans), return JSON ONLY when requested by the API consumer. Keep answers factual. Do NOT print internal context lines or 'used context' annotations in your reply.
3) If asked about past adherence, compute rates from the provided adherence lines and show the simple calculation you used (e.g., "4 taken of 6 scheduled -> 66.7%"), or return an error if insufficient data.
4) If a question is ambiguous or missing required information (timezone, medication name, dosage, frequency), ask one clarifying question instead of guessing.
5) NEVER provide medical dosing advice or recommend changing/stopping medications. If clinical interpretation is required, instruct the user to contact their clinician or pharmacist.
6) When summarizing upcoming doses, verify times against the current Time Context (provided separately) and do not suggest taking future doses earlier than scheduled without explicit user consent.

Be empathetic and concise. Avoid speculation and keep the response grounded in the provided context."""

    generic_system_prompt = """You are AdherenceGuardian. The user is asking a general, non-personal question about a medication.
Provide high-level, factual, non-prescriptive information about the medication's typical uses and mechanism of action. Do NOT give dosing recommendations or personalized medical advice. Include a brief disclaimer advising the user to consult a clinician or pharmacist for medical advice. Do NOT reference or print patient-specific context or internal 'used context' lines.
Be concise and factual."""

    if generic_med:
        messages = [{"role": "system", "content": generic_system_prompt}]
    else:
        messages = [{"role": "system", "content": default_system_prompt + context}]
    
    # Add conversation history
    # Include recent user/assistant messages (last 10)
    for msg in (request.conversation_history or [])[-10:]:
        messages.append({
            "role": msg.role,
            "content": msg.content
        })

    # Also ingest recent agent activity (last 10) for richer context
    try:
        activities = db.query(models.AgentActivity).filter(
            models.AgentActivity.patient_id == request.patient_id
        ).order_by(models.AgentActivity.timestamp.desc()).limit(10).all()
        # Prepend as system messages describing agent actions
        for act in reversed(activities):
            act_summary = act.action or (act.details or '')
            messages.append({
                "role": "system",
                "content": f"AgentActivity ({act.agent_name}): {act_summary}"
            })
    except Exception:
        # Non-blocking: ignore activity ingestion failures
        pass
    
    # Add current message
    messages.append({
        "role": "user",
        "content": request.message
    })
    
    # Determine which agent should handle this
    agent_used = _determine_agent(request.message)
    
    # Generate response
    try:
        response = await llm_service.chat(messages)
        
        # Extract any suggested actions
        suggestions = _extract_suggestions(request.message, response)
        
        return ChatResponse(
            patient_id=request.patient_id,
            response=response,
            agent_used=agent_used,
            actions_taken=None,
            suggestions=suggestions,
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating response: {str(e)}"
        )


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Stream a chat response (Server-Sent Events)
    """
    llm_service = services.get_llm_service()
    patient_service = services.get_patient_service()
    
    # Verify patient exists
    patient = await patient_service.get_patient(request.patient_id, db=db)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {request.patient_id} not found"
        )
    
    async def generate():
        system_prompt = """You are AdherenceGuardian, an AI assistant helping patients with medication adherence."""

        # Append contextual patient/profile information if requested
        if request.include_context:
            try:
                patient = await patient_service.get_patient(request.patient_id, db=db)
                summary = await patient_service.get_patient_summary(request.patient_id, db=db)
                meds = db.query(models.Medication).filter(
                    models.Medication.patient_id == request.patient_id,
                    models.Medication.active == True
                ).limit(10).all()
                med_list = '\n'.join([f"- {m.name} ({m.dosage or 'unknown'})" for m in meds]) or ' - None'

                activities = db.query(models.AgentActivity).filter(
                    models.AgentActivity.patient_id == request.patient_id
                ).order_by(models.AgentActivity.timestamp.desc()).limit(5).all()
                act_lines = '\n'.join([f"- {a.agent_name}: {a.action}" for a in activities]) or ' - None'

                context = f"\nPatient: {patient.full_name}\nTimezone: {patient.timezone}\nActive Meds:\n{med_list}\nRecent Agent Activity:\n{act_lines}\nRecent Adherence Rate: {summary.get('recent_adherence_rate','N/A')}%\n"
                system_prompt += context
            except Exception:
                # ignore context failures
                pass

        messages = [{"role": "system", "content": system_prompt}]

        # Include recent history
        for msg in (request.conversation_history or [])[-10:]:
            messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": request.message})

        try:
            async for chunk in llm_service.stream_generate(
                prompt=request.message,
                system_prompt=system_prompt
            ):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )


@router.post("/quick-action", response_model=QuickActionResponse)
async def quick_action(
    action: QuickAction,
    db: Session = Depends(get_db)
):
    """
    Execute a quick action
    
    Supported actions:
    - log_dose: Log a medication dose as taken
    - report_symptom: Quick symptom report
    - get_schedule: Get today's schedule
    - get_adherence: Get adherence summary
    """
    try:
        if action.action == "log_dose":
            adherence_service = services.get_adherence_service()
            
            params = action.parameters or {}
            schedule_id = params.get("schedule_id")
            medication_id = params.get("medication_id")
            
            if not schedule_id or not medication_id:
                return QuickActionResponse(
                    success=False,
                    action=action.action,
                    result={},
                    message="Missing schedule_id or medication_id"
                )
            
            log = await adherence_service.log_dose_taken(
                patient_id=action.patient_id,
                schedule_id=schedule_id,
                medication_id=medication_id,
                db=db
            )
            
            return QuickActionResponse(
                success=True,
                action=action.action,
                result={"log_id": log.id, "status": log.status.value},
                message="Dose logged successfully!"
            )
        
        elif action.action == "get_schedule":
            schedule_service = services.get_schedule_service()
            
            schedule = await schedule_service.get_todays_schedule(
                action.patient_id,
                db=db
            )
            
            return QuickActionResponse(
                success=True,
                action=action.action,
                result={"schedule": schedule},
                message=f"Found {len(schedule)} doses for today"
            )
        
        elif action.action == "get_adherence":
            adherence_service = services.get_adherence_service()
            
            days = (action.parameters or {}).get("days", 7)
            rate = await adherence_service.get_adherence_rate(
                action.patient_id,
                days=days,
                db=db
            )
            
            return QuickActionResponse(
                success=True,
                action=action.action,
                result=rate,
                message=f"Adherence rate: {rate['adherence_rate']}% over {days} days"
            )
        
        elif action.action == "report_symptom":
            symptom_service = services.get_symptom_service()
            from models import SeverityLevel
            
            params = action.parameters or {}
            symptom_name = params.get("symptom_name", "General discomfort")
            severity_str = params.get("severity", "moderate")
            
            severity_map = {
                "mild": SeverityLevel.LOW,
                "moderate": SeverityLevel.MEDIUM,
                "severe": SeverityLevel.HIGH,
                "critical": SeverityLevel.CRITICAL
            }
            severity = severity_map.get(severity_str, SeverityLevel.MEDIUM)
            
            report = await symptom_service.report_symptom(
                patient_id=action.patient_id,
                symptom_name=symptom_name,
                severity=severity,
                description=params.get("description"),
                medication_id=params.get("medication_id"),
                db=db
            )
            
            return QuickActionResponse(
                success=True,
                action=action.action,
                result={"report_id": report.id},
                message="Symptom reported successfully"
            )
        
        else:
            return QuickActionResponse(
                success=False,
                action=action.action,
                result={},
                message=f"Unknown action: {action.action}"
            )
    
    except Exception as e:
        return QuickActionResponse(
            success=False,
            action=action.action,
            result={"error": str(e)},
            message=f"Action failed: {str(e)}"
        )


@router.get("/suggestions/{patient_id}")
async def get_chat_suggestions(
    patient_id: int,
    db: Session = Depends(get_db)
):
    """
    Get contextual chat suggestions based on patient state
    """
    schedule_service = services.get_schedule_service()
    adherence_service = services.get_adherence_service()
    symptom_service = services.get_symptom_service()
    
    suggestions = []
    
    # Check for overdue doses
    overdue = await schedule_service.get_overdue_doses(patient_id, db=db)
    if overdue:
        suggestions.append({
            "text": f"Log missed dose for {overdue[0]['medication_name']}",
            "action": "log_dose",
            "priority": "high"
        })
    
    # Check upcoming doses
    upcoming = await schedule_service.get_upcoming_doses(patient_id, hours=2, db=db)
    if upcoming:
        suggestions.append({
            "text": f"Upcoming: {upcoming[0]['medication_name']} in {upcoming[0]['minutes_until']} min",
            "action": "view_schedule",
            "priority": "medium"
        })
    
    # Check adherence
    rate = await adherence_service.get_adherence_rate(patient_id, days=7, db=db)
    if rate["adherence_rate"] < 80:
        suggestions.append({
            "text": "View adherence tips",
            "action": "get_tips",
            "priority": "medium"
        })
    
    # Add general suggestions
    suggestions.extend([
        {"text": "View today's schedule", "action": "get_schedule", "priority": "low"},
        {"text": "Report a symptom", "action": "report_symptom", "priority": "low"},
        {"text": "Check medication interactions", "action": "check_interactions", "priority": "low"}
    ])
    
    return {
        "patient_id": patient_id,
        "suggestions": suggestions[:5]  # Top 5 suggestions
    }


@router.post("/analyze")
async def analyze_message(
    request: ChatRequest
):
    """
    Analyze a message to determine intent and extract entities
    """
    llm_service = services.get_llm_service()
    
    analysis_prompt = f"""Analyze the following message from a patient using a medication adherence app.

Message: {request.message}

Extract:
1. Primary intent (one of: log_dose, report_symptom, ask_question, schedule_inquiry, other)
2. Mentioned medications (if any)
3. Mentioned symptoms (if any)
4. Sentiment (positive, negative, neutral)
5. Urgency level (low, medium, high)

Respond in JSON format."""
    
    try:
        result = await llm_service.generate_json(
            analysis_prompt,
            system_prompt="You are an NLP analysis assistant. Respond only with valid JSON."
        )
        
        return {
            "message": request.message,
            "analysis": result,
            "suggested_agent": _determine_agent(request.message)
        }
    except Exception as e:
        return {
            "message": request.message,
            "analysis": {
                "intent": "unknown",
                "error": str(e)
            },
            "suggested_agent": "monitoring"
        }


@router.get("/activity/{activity_id}")
async def get_activity_status(activity_id: int, db: Session = Depends(get_db)):
    """Return status and payload for an AgentActivity by id."""
    act = db.query(models.AgentActivity).filter(models.AgentActivity.id == activity_id).first()
    if not act:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")

    return {
        "id": act.id,
        "patient_id": act.patient_id,
        "agent_name": act.agent_name,
        "action": act.action,
        "activity_type": act.activity_type,
        "input_data": act.input_data,
        "output_data": act.output_data,
        "is_successful": bool(act.is_successful),
        "error_message": act.error_message,
        "timestamp": act.timestamp.isoformat() if act.timestamp else None
    }


@router.get("/activities/{patient_id}")
async def list_activities(patient_id: int, limit: int = 20, db: Session = Depends(get_db)):
    """List recent AgentActivity rows for a patient (for debugging/Frontend polling)."""
    rows = db.query(models.AgentActivity).filter(models.AgentActivity.patient_id == patient_id).order_by(models.AgentActivity.timestamp.desc()).limit(limit).all()
    out = []
    for a in rows:
        out.append({
            "id": a.id,
            "agent_name": a.agent_name,
            "action": a.action,
            "activity_type": a.activity_type,
            "input_data": a.input_data,
            "output_data": a.output_data,
            "is_successful": bool(a.is_successful),
            "error_message": a.error_message,
            "timestamp": a.timestamp.isoformat() if a.timestamp else None
        })

    return {"patient_id": patient_id, "activities": out}


# ==================== HELPER FUNCTIONS ====================

def _determine_agent(message: str) -> str:
    """Determine which agent should handle the message"""
    message_lower = message.lower()
    
    # Planning agent keywords
    planning_keywords = ["schedule", "when", "time", "remind", "plan", "routine"]
    if any(kw in message_lower for kw in planning_keywords):
        return "planning"
    
    # Barrier agent keywords
    barrier_keywords = ["cost", "afford", "side effect", "forget", "difficult", "help", "problem"]
    if any(kw in message_lower for kw in barrier_keywords):
        return "barrier"
    
    # Liaison agent keywords
    liaison_keywords = ["doctor", "provider", "report", "appointment", "prescription"]
    if any(kw in message_lower for kw in liaison_keywords):
        return "liaison"
    
    # Default to monitoring agent
    return "monitoring"


def _is_generic_med_query(message: str) -> bool:
    """Return True if the user is asking a general question about a medication (not about a specific patient).

    Matches patterns like 'What does Metformin do', 'What is Paracetamol used for', and rejects
    queries that mention possessives or patient names (my, her, Emma).
    """
    m = re.search(r"what\s+(does|is)\s+([A-Za-z0-9\-]+)\s+(do|used for|used to do|for)", message.lower())
    if not m:
        return False
    # if the message references a patient or possessive, it's not generic
    if any(tok in message.lower() for tok in [" my ", " her ", " his ", " patient ", "emma", "john", "do not" ]):
        return False
    return True


def _extract_suggestions(message: str, response: str) -> List[str]:
    """Extract actionable suggestions from the conversation"""
    suggestions = []
    
    message_lower = message.lower()
    
    if "miss" in message_lower or "forgot" in message_lower:
        suggestions.append("Set up additional reminders")
        suggestions.append("Review your medication schedule")
    
    if "side effect" in message_lower or "symptom" in message_lower:
        suggestions.append("Report this symptom for tracking")
        suggestions.append("Contact your healthcare provider if severe")
    
    if "cost" in message_lower or "afford" in message_lower:
        suggestions.append("Check available assistance programs")
        suggestions.append("Ask about generic alternatives")
    
    if not suggestions:
        suggestions = [
            "View your medication schedule",
            "Check your adherence progress"
        ]
    
    return suggestions[:3]
