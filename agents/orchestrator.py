"""
Agent Orchestrator
Coordinates multiple agents using LangGraph state machine
"""

from typing import Dict, List, Optional, Any
from langgraph.graph import StateGraph, END
import logging
from datetime import datetime

from config import settings, agent_config
from database import get_db_context
import models
from agents.state import (
    AgentState, 
    create_initial_state, 
    add_agent_message, 
    update_agent_result
)

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    Orchestrates multiple specialized agents using LangGraph
    Routes tasks to appropriate agents and coordinates multi-agent workflows
    
    Architecture:
    START → Router → [Planning | Monitoring | Barrier | Liaison] → Synthesize → [Loop | END]
    """
    
    def __init__(
        self, 
        planning_agent=None, 
        monitoring_agent=None, 
        barrier_agent=None, 
        liaison_agent=None
    ):
        """
        Initialize orchestrator with agent instances
        
        Args:
            planning_agent: PlanningAgent instance
            monitoring_agent: MonitoringAgent instance
            barrier_agent: BarrierAgent instance
            liaison_agent: LiaisonAgent instance
        """
        self.planning_agent = planning_agent
        self.monitoring_agent = monitoring_agent
        self.barrier_agent = barrier_agent
        self.liaison_agent = liaison_agent
        
        # Max iterations to prevent infinite loops
        self.max_iterations = agent_config.MAX_AGENT_ITERATIONS
        
        # Build agent graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """
        Build LangGraph state machine for agent coordination
        
        Graph structure:
        START → Router → [Planning | Monitoring | Barrier | Liaison] → Synthesize → END
                  ↑                                                        │
                  └────────────────────────────────────────────────────────┘
                                    (if more agents needed)
        """
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("router", self._route_task)
        workflow.add_node("planning", self._execute_planning)
        workflow.add_node("monitoring", self._execute_monitoring)
        workflow.add_node("barrier", self._execute_barrier)
        workflow.add_node("liaison", self._execute_liaison)
        workflow.add_node("synthesize", self._synthesize_response)
        
        # Define edges
        workflow.set_entry_point("router")
        
        # Conditional routing from router
        workflow.add_conditional_edges(
            "router",
            self._determine_next_agent,
            {
                "planning": "planning",
                "monitoring": "monitoring",
                "barrier": "barrier",
                "liaison": "liaison",
                "end": END
            }
        )
        
        # All agents route to synthesizer
        workflow.add_edge("planning", "synthesize")
        workflow.add_edge("monitoring", "synthesize")
        workflow.add_edge("barrier", "synthesize")
        workflow.add_edge("liaison", "synthesize")
        
        # Synthesizer can loop back or end
        workflow.add_conditional_edges(
            "synthesize",
            self._check_if_complete,
            {
                "continue": "router",
                "end": END
            }
        )
        
        return workflow.compile()
    
    def _route_task(self, state: AgentState) -> AgentState:
        """
        Analyze task and determine which agent(s) should handle it
        Uses keyword matching with LLM fallback for classification
        """
        task = state["current_task"]
        context = state.get("context", {})
        
        # Increment iteration counter
        state["iteration_count"] = state.get("iteration_count", 0) + 1
        
        # Check if max iterations reached
        if state["iteration_count"] > self.max_iterations:
            logger.warning(f"Max iterations ({self.max_iterations}) reached, forcing end")
            state["next_agent"] = "end"
            return state
        
        # If an agent suggested the next agent, use that
        if state.get("next_agent") and state["next_agent"] != "":
            suggested = state["next_agent"]
            state = add_agent_message(
                state, "system", f"Following agent suggestion to route to {suggested}"
            )
            return state
        
        task_lower = task.lower()
        
        # Keywords for each agent
        planning_keywords = ["schedule", "timing", "when", "plan", "optimize", "replan", "medication time"]
        monitoring_keywords = ["adherence", "tracking", "pattern", "missing", "forgot", "trend", "analysis", "missed"]
        barrier_keywords = ["problem", "difficulty", "cost", "side effect", "nausea", "pain", "afford", "barrier", "help"]
        liaison_keywords = ["doctor", "report", "appointment", "provider", "medical", "escalate", "urgent", "fhir"]
        
        # Determine primary agent
        scores = {
            "planning": sum(1 for kw in planning_keywords if kw in task_lower),
            "monitoring": sum(1 for kw in monitoring_keywords if kw in task_lower),
            "barrier": sum(1 for kw in barrier_keywords if kw in task_lower),
            "liaison": sum(1 for kw in liaison_keywords if kw in task_lower)
        }
        
        # Check for escalation triggers
        if state.get("requires_escalation"):
            state["next_agent"] = "liaison"
            state = add_agent_message(
                state, "system", "Routing to liaison agent for escalation"
            )
            return state
        
        next_agent = max(scores, key=scores.get)
        
        # If all scores are 0 or tied, use LLM for classification
        if max(scores.values()) == 0 or list(scores.values()).count(max(scores.values())) > 1:
            next_agent = self._llm_classify_task(task, context)
        
        state["next_agent"] = next_agent
        state = add_agent_message(
            state, "system", f"Routing to {next_agent} agent (scores: {scores})"
        )
        
        logger.info(f"Task routed to {next_agent} agent")
        return state
    
    def _execute_planning(self, state: AgentState) -> AgentState:
        """Execute planning agent logic"""
        if not self.planning_agent:
            logger.warning("Planning agent not available")
            state["error"] = "Planning agent not configured"
            return state
        
        try:
            result_state = self.planning_agent.process(state)
            state.update(result_state)
            state["tools_used"].append("planning_agent")
            logger.info("Planning agent completed successfully")
        except Exception as e:
            logger.error(f"Planning agent error: {e}")
            state["error"] = str(e)
        
        return state
    
    def _execute_monitoring(self, state: AgentState) -> AgentState:
        """Execute monitoring agent logic"""
        if not self.monitoring_agent:
            logger.warning("Monitoring agent not available")
            state["error"] = "Monitoring agent not configured"
            return state
        
        try:
            result_state = self.monitoring_agent.process(state)
            state.update(result_state)
            state["tools_used"].append("monitoring_agent")
            logger.info("Monitoring agent completed successfully")
        except Exception as e:
            logger.error(f"Monitoring agent error: {e}")
            state["error"] = str(e)
        
        return state
    
    def _execute_barrier(self, state: AgentState) -> AgentState:
        """Execute barrier resolution agent logic"""
        if not self.barrier_agent:
            logger.warning("Barrier agent not available")
            state["error"] = "Barrier agent not configured"
            return state
        
        try:
            result_state = self.barrier_agent.process(state)
            state.update(result_state)
            state["tools_used"].append("barrier_agent")
            logger.info("Barrier agent completed successfully")
        except Exception as e:
            logger.error(f"Barrier agent error: {e}")
            state["error"] = str(e)
        
        return state
    
    def _execute_liaison(self, state: AgentState) -> AgentState:
        """Execute healthcare liaison agent logic"""
        if not self.liaison_agent:
            logger.warning("Liaison agent not available")
            state["error"] = "Liaison agent not configured"
            return state
        
        try:
            result_state = self.liaison_agent.process(state)
            state.update(result_state)
            state["tools_used"].append("liaison_agent")
            logger.info("Liaison agent completed successfully")
        except Exception as e:
            logger.error(f"Liaison agent error: {e}")
            state["error"] = str(e)
        
        return state
    
    def _synthesize_response(self, state: AgentState) -> AgentState:
        """
        Synthesize results from multiple agents into coherent response
        Determines if additional agents need to be called
        """
        context = state.get("context", {})
        agent_results = state.get("agent_results", {})
        
        # Check if any agent suggested a follow-up agent
        next_suggestion = None
        for agent_name, result in agent_results.items():
            if isinstance(result, dict) and result.get("next_agent_suggestion"):
                next_suggestion = result["next_agent_suggestion"]
                break
        
        # Check if all necessary information has been gathered
        needs_more_agents = self._check_dependencies(context, agent_results)
        
        if needs_more_agents:
            state["next_agent"] = needs_more_agents
            state = add_agent_message(
                state, "system", f"Dependency check requires {needs_more_agents} agent"
            )
            return state
        
        if next_suggestion and next_suggestion not in state["tools_used"]:
            state["next_agent"] = next_suggestion
            state = add_agent_message(
                state, "system", f"Following up with {next_suggestion} agent as suggested"
            )
            return state
        
        # Generate final response by combining agent outputs
        final_response = self._combine_agent_responses(context, agent_results)
        state["final_response"] = final_response
        state["confidence"] = self._calculate_confidence(agent_results)
        
        # Clear next_agent to signal completion
        state["next_agent"] = ""
        
        logger.info(f"Response synthesized with confidence {state['confidence']:.2f}")
        return state
    
    def _determine_next_agent(self, state: AgentState) -> str:
        """Determine which agent node to execute next"""
        next_agent = state.get("next_agent", "")
        
        # Validate agent name
        if next_agent in ["planning", "monitoring", "barrier", "liaison"]:
            return next_agent
        
        # Default to end if invalid or empty
        return "end"
    
    def _check_if_complete(self, state: AgentState) -> str:
        """Check if workflow is complete or needs more agents"""
        # If we have a final response, we're done
        if state.get("final_response"):
            return "end"
        
        # If there's a next agent specified, continue
        if state.get("next_agent") and state["next_agent"] in ["planning", "monitoring", "barrier", "liaison"]:
            return "continue"
        
        # If max iterations reached, end
        if state.get("iteration_count", 0) >= self.max_iterations:
            return "end"
        
        return "end"
    
    def _llm_classify_task(self, task: str, context: Dict) -> str:
        """Use LLM to classify task when keyword matching is unclear"""
        # Import here to avoid circular imports
        try:
            from anthropic import Anthropic
            
            client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            
            prompt = f"""Classify the following task into exactly one of these categories:
- planning: Medication scheduling, timing optimization, replanning
- monitoring: Adherence tracking, pattern analysis, progress monitoring  
- barrier: Problem resolution, side effects, cost issues, obstacles
- liaison: Provider communication, medical reports, clinical summaries

Task: "{task}"
Context: {context}

Return only the single category name (planning, monitoring, barrier, or liaison)."""
            
            message = client.messages.create(
                model=settings.LLM_MODEL,
                max_tokens=50,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response = message.content[0].text.strip().lower()
            
            # Validate response
            if response in ["planning", "monitoring", "barrier", "liaison"]:
                return response
            
        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
        
        # Default fallback
        return "monitoring"
    
    def _check_dependencies(self, context: Dict, agent_results: Dict) -> Optional[str]:
        """
        Check if additional agents are needed based on current context
        Example: Side effect report might need both monitoring AND barrier agents
        """
        # If barrier agent found cost issue, might need planning agent
        if "barrier" in agent_results:
            barrier_result = agent_results["barrier"]
            if isinstance(barrier_result, dict):
                if barrier_result.get("requires_schedule_change") and "planning" not in context:
                    return "planning"
        
        # If monitoring found low adherence, might need barrier agent
        if "monitoring" in agent_results:
            monitoring_result = agent_results["monitoring"]
            if isinstance(monitoring_result, dict):
                data = monitoring_result.get("data", {})
                if data.get("adherence_rate", 100) < 70 and "barrier" not in context:
                    return "barrier"
        
        # If escalation needed, ensure liaison is called
        if context.get("requires_escalation") and "liaison" not in agent_results:
            return "liaison"
        
        return None
    
    def _combine_agent_responses(self, context: Dict, agent_results: Dict) -> str:
        """Combine outputs from multiple agents into coherent response"""
        responses = []
        
        for agent_name, result in agent_results.items():
            if isinstance(result, dict) and result.get("summary"):
                responses.append(f"**{agent_name.title()}**: {result['summary']}")
        
        # Also check context for legacy format
        if "planning_result" in context:
            result = context["planning_result"]
            if isinstance(result, dict) and result.get("summary"):
                responses.append(f"**Schedule**: {result['summary']}")
        
        if "monitoring_result" in context:
            result = context["monitoring_result"]
            if isinstance(result, dict) and result.get("summary"):
                responses.append(f"**Analysis**: {result['summary']}")
        
        if "barrier_result" in context:
            result = context["barrier_result"]
            if isinstance(result, dict):
                summary = result.get("summary") or result.get("recommendation", "")
                if summary:
                    responses.append(f"**Solution**: {summary}")
        
        if "liaison_result" in context:
            result = context["liaison_result"]
            if isinstance(result, dict) and result.get("summary"):
                responses.append(f"**Provider Update**: {result['summary']}")
        
        return "\n\n".join(responses) if responses else "I've analyzed your request but couldn't generate a specific response."
    
    def _calculate_confidence(self, agent_results: Dict) -> float:
        """Calculate overall confidence in the response"""
        confidences = []
        
        for agent_name, result in agent_results.items():
            if isinstance(result, dict) and "confidence" in result:
                confidences.append(result["confidence"])
        
        return sum(confidences) / len(confidences) if confidences else 0.5
    
    async def route_chat_message(self, patient_id: int, message: str) -> Dict:
        """
        Main entry point for processing user messages
        Routes through agent graph
        
        Args:
            patient_id: Patient identifier
            message: User message to process
            
        Returns:
            Dict with response, agent info, and actions
        """
        # Create initial state using helper
        initial_state = create_initial_state(patient_id, message)
        
        try:
            # Execute graph
            final_state = self.graph.invoke(initial_state)
            
            # Log orchestration activity
            with get_db_context() as db:
                activity = models.AgentActivity(
                    patient_id=patient_id,
                    agent_type=models.AgentType.ORCHESTRATOR,
                    agent_name="Orchestrator",
                    action="route_chat_message",
                    activity_type="orchestration",
                    input_data={"message": message},
                    output_data={
                        "tools_used": final_state.get("tools_used", []),
                        "confidence": final_state.get("confidence", 0.0)
                    }
                )
                db.add(activity)
                db.commit()
            
            return {
                "text": final_state.get("final_response", "I'm sorry, I couldn't process that request."),
                "agent_name": final_state["tools_used"][-1] if final_state.get("tools_used") else "orchestrator",
                "confidence": final_state.get("confidence", 0.0),
                "actions": self._extract_actions(final_state),
                "agent_results": final_state.get("agent_results", {})
            }
            
        except Exception as e:
            logger.error(f"Error routing chat message: {e}")
            return {
                "text": "I apologize, but I encountered an error processing your request. Please try again.",
                "agent_name": "orchestrator",
                "confidence": 0.0,
                "actions": [],
                "error": str(e)
            }
    
    def _extract_actions(self, state: AgentState) -> List[Dict]:
        """Extract actionable items from agent results"""
        actions = []
        
        context = state.get("context", {})
        agent_results = state.get("agent_results", {})
        
        # Extract actions from each agent's results
        for agent_name, result in agent_results.items():
            if not isinstance(result, dict):
                continue
            
            # Check for recommendations
            if result.get("recommendations"):
                for rec in result["recommendations"]:
                    actions.append({
                        "type": "recommendation",
                        "source": agent_name,
                        "description": rec
                    })
            
            # Check for schedule updates
            if result.get("schedule_updated"):
                actions.append({
                    "type": "schedule_update",
                    "source": agent_name,
                    "description": "Medication schedule has been optimized"
                })
            
            # Check for escalations
            if result.get("requires_escalation"):
                actions.append({
                    "type": "escalation",
                    "source": agent_name,
                    "description": "This issue has been escalated to your healthcare provider"
                })
        
        # Also check context for legacy format
        if "planning_result" in context:
            if context["planning_result"].get("schedule_updated"):
                actions.append({
                    "type": "schedule_update",
                    "source": "planning",
                    "description": "Medication schedule has been optimized"
                })
        
        if "barrier_result" in context:
            if context["barrier_result"].get("recommendations"):
                for rec in context["barrier_result"]["recommendations"]:
                    if rec not in [a.get("description") for a in actions]:
                        actions.append({
                            "type": "recommendation",
                            "source": "barrier",
                            "description": rec
                        })
        
        return actions
    
    async def handle_new_medication(self, patient_id: int, medication_id: int) -> Dict:
        """
        Handle new medication addition workflow
        
        Args:
            patient_id: Patient identifier
            medication_id: New medication ID
            
        Returns:
            Dict with scheduling results
        """
        state = create_initial_state(
            patient_id=patient_id,
            task=f"optimize schedule for new medication {medication_id}"
        )
        state["context"]["medication_id"] = medication_id
        state["next_agent"] = "planning"
        
        try:
            # Execute planning agent directly
            result = self.graph.invoke(state)
            
            return {
                "success": True,
                "schedule_updated": result.get("context", {}).get("planning_result", {}).get("schedule_updated", False),
                "summary": result.get("final_response", "Schedule updated"),
                "agent_results": result.get("agent_results", {})
            }
            
        except Exception as e:
            logger.error(f"Error handling new medication: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_insights(self, patient_id: int) -> List[Dict]:
        """
        Generate AI insights by coordinating multiple agents
        Uses monitoring agent for patterns, barrier for issues, liaison for recommendations
        
        Args:
            patient_id: Patient identifier
            
        Returns:
            List of insight dictionaries
        """
        insights = []
        
        try:
            # Get monitoring insights
            monitoring_state = create_initial_state(
                patient_id=patient_id,
                task="analyze adherence patterns and trends"
            )
            monitoring_state["next_agent"] = "monitoring"
            
            monitoring_result = self.graph.invoke(monitoring_state)
            
            monitoring_data = monitoring_result.get("agent_results", {}).get("monitoring", {})
            if monitoring_data:
                data = monitoring_data.get("data", {})
                
                # Add adherence insight
                adherence_rate = data.get("adherence_rate", 0)
                insights.append({
                    "type": "adherence",
                    "title": "Adherence Rate",
                    "value": f"{adherence_rate}%",
                    "status": "good" if adherence_rate >= 90 else "warning" if adherence_rate >= 70 else "critical",
                    "description": monitoring_data.get("summary", "")
                })
                
                # Add trend insight
                trend = data.get("trend", "stable")
                insights.append({
                    "type": "trend",
                    "title": "Trend",
                    "value": trend.title(),
                    "status": "good" if trend == "improving" else "warning" if trend == "stable" else "critical"
                })
            
            # Get barrier insights
            barrier_state = create_initial_state(
                patient_id=patient_id,
                task="identify potential adherence barriers"
            )
            barrier_state["next_agent"] = "barrier"
            
            barrier_result = self.graph.invoke(barrier_state)
            
            barrier_data = barrier_result.get("agent_results", {}).get("barrier", {})
            if barrier_data and barrier_data.get("data", {}).get("barriers"):
                barriers = barrier_data["data"]["barriers"]
                insights.append({
                    "type": "barriers",
                    "title": "Identified Barriers",
                    "value": str(len(barriers)),
                    "status": "warning" if barriers else "good",
                    "description": f"Found {len(barriers)} barrier(s) to address",
                    "details": barriers[:3]  # Top 3 barriers
                })
            
        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            insights.append({
                "type": "error",
                "title": "Analysis Error",
                "value": "N/A",
                "status": "critical",
                "description": "Unable to generate insights at this time"
            })
        
        return insights
    
    async def handle_symptom_report(self, patient_id: int, symptom_id: int) -> Dict:
        """
        Handle a new symptom report through the agent system
        
        Args:
            patient_id: Patient identifier
            symptom_id: Symptom report ID
            
        Returns:
            Dict with analysis and recommendations
        """
        state = create_initial_state(
            patient_id=patient_id,
            task=f"analyze symptom report and determine if it's medication related"
        )
        state["context"]["symptom_id"] = symptom_id
        state["next_agent"] = "monitoring"
        
        try:
            result = self.graph.invoke(state)
            
            # Check if escalation is needed
            monitoring_result = result.get("agent_results", {}).get("monitoring", {})
            if monitoring_result.get("requires_escalation"):
                # Run liaison agent for escalation
                state["current_task"] = "escalate symptom to provider"
                state["next_agent"] = "liaison"
                result = self.graph.invoke(state)
            
            return {
                "success": True,
                "analysis": monitoring_result,
                "escalated": monitoring_result.get("requires_escalation", False),
                "recommendations": monitoring_result.get("recommendations", [])
            }
            
        except Exception as e:
            logger.error(f"Error handling symptom report: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def is_healthy(self) -> bool:
        """Health check for the orchestrator"""
        try:
            # Check if graph is compiled
            if self.graph is None:
                return False
            
            # Check agent health
            agents_healthy = True
            
            if self.planning_agent:
                agents_healthy = agents_healthy and self.planning_agent.is_healthy()
            if self.monitoring_agent:
                agents_healthy = agents_healthy and self.monitoring_agent.is_healthy()
            if self.barrier_agent:
                agents_healthy = agents_healthy and self.barrier_agent.is_healthy()
            if self.liaison_agent:
                agents_healthy = agents_healthy and self.liaison_agent.is_healthy()
            
            return agents_healthy
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False