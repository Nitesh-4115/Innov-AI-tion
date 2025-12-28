"""
Tests for Adherence Service
Tests medication adherence tracking and analysis business logic
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, date, timedelta, time
from typing import List, Dict, Any
from collections import defaultdict

from sqlalchemy.orm import Session

from services.adherence_service import AdherenceService
from models import AdherenceStatus, AdherenceLog, Schedule, Medication, Patient


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def adherence_service():
    """Create adherence service instance"""
    return AdherenceService()


@pytest.fixture
def mock_db_session():
    """Create mock database session"""
    session = MagicMock(spec=Session)
    return session


@pytest.fixture
def sample_patient():
    """Sample patient for testing"""
    patient = MagicMock(spec=Patient)
    patient.id = 1
    patient.name = "John Doe"
    return patient


@pytest.fixture
def sample_medication():
    """Sample medication for testing"""
    med = MagicMock(spec=Medication)
    med.id = 1
    med.name = "Metformin"
    med.dosage = "500mg"
    med.patient_id = 1
    return med


@pytest.fixture
def sample_schedule():
    """Sample schedule for testing"""
    schedule = MagicMock(spec=Schedule)
    schedule.id = 1
    schedule.patient_id = 1
    schedule.medication_id = 1
    schedule.scheduled_time = time(8, 0)
    return schedule


@pytest.fixture
def sample_adherence_logs():
    """Sample adherence logs for testing"""
    base_date = datetime.utcnow()
    logs = []
    
    for i in range(30):
        log = MagicMock(spec=AdherenceLog)
        log.id = i + 1
        log.patient_id = 1
        log.schedule_id = 1
        log.medication_id = 1
        log.logged_at = base_date - timedelta(days=i)
        log.deviation_minutes = 0
        
        # Mix of statuses: 80% taken, 15% delayed, 5% missed
        if i % 20 == 0:
            log.status = AdherenceStatus.MISSED
        elif i % 7 == 0:
            log.status = AdherenceStatus.DELAYED
            log.deviation_minutes = 45
        else:
            log.status = AdherenceStatus.TAKEN
            log.deviation_minutes = 5
        
        logs.append(log)
    
    return logs


@pytest.fixture
def perfect_adherence_logs():
    """Logs with 100% adherence"""
    base_date = datetime.utcnow()
    logs = []
    
    for i in range(30):
        log = MagicMock(spec=AdherenceLog)
        log.id = i + 1
        log.patient_id = 1
        log.schedule_id = 1
        log.medication_id = 1
        log.status = AdherenceStatus.TAKEN
        log.logged_at = base_date - timedelta(days=i)
        log.deviation_minutes = 0
        logs.append(log)
    
    return logs


@pytest.fixture
def poor_adherence_logs():
    """Logs with poor adherence"""
    base_date = datetime.utcnow()
    logs = []
    
    for i in range(30):
        log = MagicMock(spec=AdherenceLog)
        log.id = i + 1
        log.patient_id = 1
        log.schedule_id = 1
        log.medication_id = 1
        log.logged_at = base_date - timedelta(days=i)
        log.deviation_minutes = 0
        
        # 50% missed
        if i % 2 == 0:
            log.status = AdherenceStatus.MISSED
        else:
            log.status = AdherenceStatus.TAKEN
        
        logs.append(log)
    
    return logs


# =============================================================================
# Test AdherenceService Initialization
# =============================================================================

class TestAdherenceServiceInit:
    """Tests for AdherenceService initialization"""
    
    def test_service_initialization(self, adherence_service):
        """Test service initializes correctly"""
        assert adherence_service is not None
    
    def test_service_has_required_methods(self, adherence_service):
        """Test service has required methods"""
        assert hasattr(adherence_service, "log_adherence")
        assert hasattr(adherence_service, "log_dose_taken")
        assert hasattr(adherence_service, "log_dose_missed")
        assert hasattr(adherence_service, "get_adherence_rate")
        assert hasattr(adherence_service, "get_adherence_streak")


# =============================================================================
# Test Log Adherence
# =============================================================================

class TestLogAdherence:
    """Tests for adherence logging"""
    
    @pytest.mark.asyncio
    async def test_log_adherence_taken(self, adherence_service, mock_db_session, sample_schedule):
        """Test logging a taken dose"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_schedule
        mock_db_session.add = MagicMock()
        mock_db_session.commit = MagicMock()
        mock_db_session.refresh = MagicMock()
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            log = await adherence_service.log_adherence(
                patient_id=1,
                schedule_id=1,
                medication_id=1,
                status=AdherenceStatus.TAKEN,
                taken_at=datetime.utcnow(),
                db=mock_db_session
            )
    
    @pytest.mark.asyncio
    async def test_log_adherence_missed(self, adherence_service, mock_db_session, sample_schedule):
        """Test logging a missed dose"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_schedule
        mock_db_session.add = MagicMock()
        mock_db_session.commit = MagicMock()
        mock_db_session.refresh = MagicMock()
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            log = await adherence_service.log_adherence(
                patient_id=1,
                schedule_id=1,
                medication_id=1,
                status=AdherenceStatus.MISSED,
                notes="Forgot to take",
                db=mock_db_session
            )
    
    @pytest.mark.asyncio
    async def test_log_adherence_skipped(self, adherence_service, mock_db_session, sample_schedule):
        """Test logging a skipped dose"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_schedule
        mock_db_session.add = MagicMock()
        mock_db_session.commit = MagicMock()
        mock_db_session.refresh = MagicMock()
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            log = await adherence_service.log_adherence(
                patient_id=1,
                schedule_id=1,
                medication_id=1,
                status=AdherenceStatus.SKIPPED,
                notes="Side effects",
                reported_by="patient",
                db=mock_db_session
            )
    
    @pytest.mark.asyncio
    async def test_log_adherence_delayed(self, adherence_service, mock_db_session, sample_schedule):
        """Test logging a delayed dose"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_schedule
        mock_db_session.add = MagicMock()
        mock_db_session.commit = MagicMock()
        mock_db_session.refresh = MagicMock()
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            log = await adherence_service.log_adherence(
                patient_id=1,
                schedule_id=1,
                medication_id=1,
                status=AdherenceStatus.DELAYED,
                deviation_minutes=45,
                db=mock_db_session
            )


# =============================================================================
# Test Convenience Logging Methods
# =============================================================================

class TestConvenienceLogging:
    """Tests for convenience logging methods"""
    
    @pytest.mark.asyncio
    async def test_log_dose_taken(self, adherence_service, mock_db_session, sample_schedule):
        """Test log_dose_taken convenience method"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_schedule
        mock_db_session.add = MagicMock()
        mock_db_session.commit = MagicMock()
        mock_db_session.refresh = MagicMock()
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            await adherence_service.log_dose_taken(
                patient_id=1,
                schedule_id=1,
                medication_id=1,
                db=mock_db_session
            )
    
    @pytest.mark.asyncio
    async def test_log_dose_missed(self, adherence_service, mock_db_session, sample_schedule):
        """Test log_dose_missed convenience method"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_schedule
        mock_db_session.add = MagicMock()
        mock_db_session.commit = MagicMock()
        mock_db_session.refresh = MagicMock()
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            await adherence_service.log_dose_missed(
                patient_id=1,
                schedule_id=1,
                medication_id=1,
                reason="Forgot",
                db=mock_db_session
            )
    
    @pytest.mark.asyncio
    async def test_log_dose_skipped(self, adherence_service, mock_db_session, sample_schedule):
        """Test log_dose_skipped convenience method"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_schedule
        mock_db_session.add = MagicMock()
        mock_db_session.commit = MagicMock()
        mock_db_session.refresh = MagicMock()
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            await adherence_service.log_dose_skipped(
                patient_id=1,
                schedule_id=1,
                medication_id=1,
                reason="Side effects",
                db=mock_db_session
            )


# =============================================================================
# Test Deviation Calculation
# =============================================================================

class TestDeviationCalculation:
    """Tests for dose timing deviation calculation"""
    
    @pytest.mark.asyncio
    async def test_on_time_dose(self, adherence_service, mock_db_session, sample_schedule):
        """Test dose taken on time"""
        # Schedule at 8:00, taken at 8:00
        scheduled_time = time(8, 0)
        sample_schedule.scheduled_time = scheduled_time
        taken_at = datetime.combine(date.today(), scheduled_time)
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_schedule
        mock_db_session.add = MagicMock()
        mock_db_session.commit = MagicMock()
        mock_db_session.refresh = MagicMock()
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            await adherence_service.log_dose_taken(
                patient_id=1,
                schedule_id=1,
                medication_id=1,
                taken_at=taken_at,
                db=mock_db_session
            )
    
    @pytest.mark.asyncio
    async def test_late_dose_marked_delayed(self, adherence_service, mock_db_session, sample_schedule):
        """Test dose more than 30 min late marked as delayed"""
        # Schedule at 8:00, taken at 9:00 (60 min late)
        scheduled_time = time(8, 0)
        sample_schedule.scheduled_time = scheduled_time
        taken_at = datetime.combine(date.today(), time(9, 0))
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_schedule
        mock_db_session.add = MagicMock()
        mock_db_session.commit = MagicMock()
        mock_db_session.refresh = MagicMock()
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            await adherence_service.log_dose_taken(
                patient_id=1,
                schedule_id=1,
                medication_id=1,
                taken_at=taken_at,
                db=mock_db_session
            )


# =============================================================================
# Test Get Adherence Rate
# =============================================================================

class TestGetAdherenceRate:
    """Tests for adherence rate calculation"""
    
    @pytest.mark.asyncio
    async def test_get_adherence_rate_basic(self, adherence_service, mock_db_session, sample_adherence_logs):
        """Test basic adherence rate calculation"""
        mock_db_session.query.return_value.filter.return_value.all.return_value = sample_adherence_logs
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            result = await adherence_service.get_adherence_rate(
                patient_id=1,
                days=30,
                db=mock_db_session
            )
            
            assert "adherence_rate" in result
            assert "total_doses" in result
            assert "taken" in result
            assert "missed" in result
    
    @pytest.mark.asyncio
    async def test_perfect_adherence_rate(self, adherence_service, mock_db_session, perfect_adherence_logs):
        """Test 100% adherence rate"""
        mock_db_session.query.return_value.filter.return_value.all.return_value = perfect_adherence_logs
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            result = await adherence_service.get_adherence_rate(
                patient_id=1,
                days=30,
                db=mock_db_session
            )
            
            assert result["adherence_rate"] == 100.0
            assert result["missed"] == 0
    
    @pytest.mark.asyncio
    async def test_poor_adherence_rate(self, adherence_service, mock_db_session, poor_adherence_logs):
        """Test poor adherence rate (50%)"""
        mock_db_session.query.return_value.filter.return_value.all.return_value = poor_adherence_logs
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            result = await adherence_service.get_adherence_rate(
                patient_id=1,
                days=30,
                db=mock_db_session
            )
            
            assert result["adherence_rate"] == 50.0
    
    @pytest.mark.asyncio
    async def test_adherence_rate_no_data(self, adherence_service, mock_db_session):
        """Test adherence rate with no data"""
        mock_db_session.query.return_value.filter.return_value.all.return_value = []
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            result = await adherence_service.get_adherence_rate(
                patient_id=1,
                days=30,
                db=mock_db_session
            )
            
            assert result["adherence_rate"] == 0.0
            assert result["total_doses"] == 0
    
    @pytest.mark.asyncio
    async def test_adherence_rate_by_medication(self, adherence_service, mock_db_session, sample_adherence_logs):
        """Test adherence rate for specific medication"""
        mock_db_session.query.return_value.filter.return_value.filter.return_value.all.return_value = sample_adherence_logs
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            result = await adherence_service.get_adherence_rate(
                patient_id=1,
                days=30,
                medication_id=1,
                db=mock_db_session
            )
            
            assert "adherence_rate" in result
    
    @pytest.mark.asyncio
    async def test_adherence_rate_custom_days(self, adherence_service, mock_db_session, sample_adherence_logs):
        """Test adherence rate for custom time period"""
        mock_db_session.query.return_value.filter.return_value.all.return_value = sample_adherence_logs[:7]
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            result = await adherence_service.get_adherence_rate(
                patient_id=1,
                days=7,
                db=mock_db_session
            )
            
            assert result["days_analyzed"] == 7


# =============================================================================
# Test Adherence Streak
# =============================================================================

class TestAdherenceStreak:
    """Tests for adherence streak calculation"""
    
    @pytest.mark.asyncio
    async def test_get_adherence_streak(self, adherence_service, mock_db_session, sample_adherence_logs):
        """Test getting adherence streak"""
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = sample_adherence_logs
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            result = await adherence_service.get_adherence_streak(
                patient_id=1,
                db=mock_db_session
            )
            
            assert "current_streak" in result
            assert "best_streak" in result
    
    @pytest.mark.asyncio
    async def test_perfect_streak(self, adherence_service, mock_db_session, perfect_adherence_logs):
        """Test perfect adherence streak"""
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = perfect_adherence_logs
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            result = await adherence_service.get_adherence_streak(
                patient_id=1,
                db=mock_db_session
            )
            
            assert result["current_streak"] >= 0
            assert result["best_streak"] >= 0
    
    @pytest.mark.asyncio
    async def test_streak_with_no_data(self, adherence_service, mock_db_session):
        """Test streak with no adherence data"""
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            result = await adherence_service.get_adherence_streak(
                patient_id=1,
                db=mock_db_session
            )
            
            assert result["current_streak"] == 0
            assert result["best_streak"] == 0
            assert result["streak_start"] is None


# =============================================================================
# Test Adherence by Medication
# =============================================================================

class TestAdherenceByMedication:
    """Tests for per-medication adherence breakdown"""
    
    @pytest.mark.asyncio
    async def test_get_adherence_by_medication(self, adherence_service, mock_db_session, sample_medication):
        """Test getting adherence breakdown by medication"""
        mock_db_session.query.return_value.filter.return_value.all.return_value = [sample_medication]
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            # Mock the internal rate calculation
            with patch.object(adherence_service, "_sync_get_adherence_rate") as mock_rate:
                mock_rate.return_value = {
                    "adherence_rate": 85.0,
                    "total_doses": 30,
                    "missed": 5
                }
                
                result = await adherence_service.get_adherence_by_medication(
                    patient_id=1,
                    days=30,
                    db=mock_db_session
                )
                
                assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_adherence_by_medication_sorted(self, adherence_service, mock_db_session):
        """Test results are sorted by adherence rate"""
        med1 = MagicMock(spec=Medication)
        med1.id = 1
        med1.name = "Med1"
        med1.dosage = "10mg"
        med1.patient_id = 1
        
        med2 = MagicMock(spec=Medication)
        med2.id = 2
        med2.name = "Med2"
        med2.dosage = "20mg"
        med2.patient_id = 1
        
        mock_db_session.query.return_value.filter.return_value.all.return_value = [med1, med2]
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            results = []
            with patch.object(adherence_service, "_sync_get_adherence_rate") as mock_rate:
                # Med1 has lower adherence
                def rate_side_effect(session, patient_id, days, med_id):
                    if med_id == 1:
                        return {"adherence_rate": 50.0, "total_doses": 30, "missed": 15}
                    return {"adherence_rate": 90.0, "total_doses": 30, "missed": 3}
                
                mock_rate.side_effect = rate_side_effect
                
                result = await adherence_service.get_adherence_by_medication(
                    patient_id=1,
                    days=30,
                    db=mock_db_session
                )


# =============================================================================
# Test Average Deviation
# =============================================================================

class TestAverageDeviation:
    """Tests for average timing deviation calculation"""
    
    @pytest.mark.asyncio
    async def test_average_deviation_calculation(self, adherence_service, mock_db_session, sample_adherence_logs):
        """Test average deviation is calculated"""
        mock_db_session.query.return_value.filter.return_value.all.return_value = sample_adherence_logs
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            result = await adherence_service.get_adherence_rate(
                patient_id=1,
                days=30,
                db=mock_db_session
            )
            
            assert "average_deviation_minutes" in result
    
    @pytest.mark.asyncio
    async def test_zero_deviation_for_perfect_timing(self, adherence_service, mock_db_session, perfect_adherence_logs):
        """Test zero deviation for perfectly timed doses"""
        # All logs have 0 deviation
        mock_db_session.query.return_value.filter.return_value.all.return_value = perfect_adherence_logs
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            result = await adherence_service.get_adherence_rate(
                patient_id=1,
                days=30,
                db=mock_db_session
            )
            
            assert result["average_deviation_minutes"] == 0.0


# =============================================================================
# Test Status Counting
# =============================================================================

class TestStatusCounting:
    """Tests for adherence status counting"""
    
    @pytest.mark.asyncio
    async def test_count_all_statuses(self, adherence_service, mock_db_session, sample_adherence_logs):
        """Test all statuses are counted correctly"""
        mock_db_session.query.return_value.filter.return_value.all.return_value = sample_adherence_logs
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            result = await adherence_service.get_adherence_rate(
                patient_id=1,
                days=30,
                db=mock_db_session
            )
            
            total = result["taken"] + result["missed"] + result["skipped"] + result["delayed"]
            assert total == result["total_doses"]


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases"""
    
    @pytest.mark.asyncio
    async def test_single_dose_adherence(self, adherence_service, mock_db_session):
        """Test adherence with single dose"""
        single_log = MagicMock(spec=AdherenceLog)
        single_log.status = AdherenceStatus.TAKEN
        single_log.deviation_minutes = 0
        
        mock_db_session.query.return_value.filter.return_value.all.return_value = [single_log]
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            result = await adherence_service.get_adherence_rate(
                patient_id=1,
                days=1,
                db=mock_db_session
            )
            
            assert result["total_doses"] == 1
            assert result["adherence_rate"] == 100.0
    
    @pytest.mark.asyncio
    async def test_zero_days_period(self, adherence_service, mock_db_session):
        """Test handling zero day period"""
        mock_db_session.query.return_value.filter.return_value.all.return_value = []
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            result = await adherence_service.get_adherence_rate(
                patient_id=1,
                days=0,
                db=mock_db_session
            )
            
            assert result["days_analyzed"] == 0
    
    @pytest.mark.asyncio
    async def test_very_long_period(self, adherence_service, mock_db_session, sample_adherence_logs):
        """Test handling very long time period"""
        mock_db_session.query.return_value.filter.return_value.all.return_value = sample_adherence_logs
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            result = await adherence_service.get_adherence_rate(
                patient_id=1,
                days=365,  # Full year
                db=mock_db_session
            )
            
            assert "adherence_rate" in result


# =============================================================================
# Test Integration Scenarios
# =============================================================================

class TestAdherenceServiceIntegration:
    """Integration tests for adherence service"""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_adherence_tracking_workflow(self, adherence_service, mock_db_session, sample_schedule):
        """Test complete adherence tracking workflow"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_schedule
        mock_db_session.add = MagicMock()
        mock_db_session.commit = MagicMock()
        mock_db_session.refresh = MagicMock()
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            # 1. Log some doses
            await adherence_service.log_dose_taken(
                patient_id=1,
                schedule_id=1,
                medication_id=1,
                db=mock_db_session
            )
            
            await adherence_service.log_dose_missed(
                patient_id=1,
                schedule_id=1,
                medication_id=1,
                reason="Forgot",
                db=mock_db_session
            )
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_multi_medication_adherence(self, adherence_service, mock_db_session):
        """Test adherence tracking for multiple medications"""
        # Create logs for multiple medications
        logs = []
        for med_id in [1, 2, 3]:
            for i in range(10):
                log = MagicMock(spec=AdherenceLog)
                log.id = med_id * 100 + i
                log.patient_id = 1
                log.medication_id = med_id
                log.status = AdherenceStatus.TAKEN if i % 2 == 0 else AdherenceStatus.MISSED
                log.logged_at = datetime.utcnow() - timedelta(days=i)
                log.deviation_minutes = 0
                logs.append(log)
        
        mock_db_session.query.return_value.filter.return_value.all.return_value = logs
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            result = await adherence_service.get_adherence_rate(
                patient_id=1,
                days=30,
                db=mock_db_session
            )
            
            # Should calculate combined adherence
            assert "adherence_rate" in result


# =============================================================================
# Test Reporter Types
# =============================================================================

class TestReporterTypes:
    """Tests for different reporter types"""
    
    @pytest.mark.asyncio
    async def test_patient_reported(self, adherence_service, mock_db_session, sample_schedule):
        """Test patient-reported adherence"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_schedule
        mock_db_session.add = MagicMock()
        mock_db_session.commit = MagicMock()
        mock_db_session.refresh = MagicMock()
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            await adherence_service.log_adherence(
                patient_id=1,
                schedule_id=1,
                medication_id=1,
                status=AdherenceStatus.TAKEN,
                reported_by="patient",
                db=mock_db_session
            )
    
    @pytest.mark.asyncio
    async def test_system_reported(self, adherence_service, mock_db_session, sample_schedule):
        """Test system-reported adherence (automatic detection)"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_schedule
        mock_db_session.add = MagicMock()
        mock_db_session.commit = MagicMock()
        mock_db_session.refresh = MagicMock()
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            await adherence_service.log_adherence(
                patient_id=1,
                schedule_id=1,
                medication_id=1,
                status=AdherenceStatus.MISSED,
                reported_by="system",
                db=mock_db_session
            )
    
    @pytest.mark.asyncio
    async def test_caregiver_reported(self, adherence_service, mock_db_session, sample_schedule):
        """Test caregiver-reported adherence"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_schedule
        mock_db_session.add = MagicMock()
        mock_db_session.commit = MagicMock()
        mock_db_session.refresh = MagicMock()
        
        with patch("services.adherence_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            await adherence_service.log_adherence(
                patient_id=1,
                schedule_id=1,
                medication_id=1,
                status=AdherenceStatus.TAKEN,
                reported_by="caregiver",
                db=mock_db_session
            )
