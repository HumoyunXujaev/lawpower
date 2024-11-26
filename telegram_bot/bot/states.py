from aiogram.fsm.state import State, StatesGroup

class BaseState(StatesGroup):
    """Base state group with common functionality"""
    @classmethod
    def get_state_names(cls) -> list[str]:
        return [attr for attr in dir(cls) if isinstance(getattr(cls, attr), State)]
        
    @classmethod
    def get_state(cls, name: str) -> Optional[State]:
        return getattr(cls, name, None) if name in cls.get_state_names() else None

class UserState(BaseState):
    """User interaction states"""
    initial = State()
    selecting_language = State()
    entering_name = State()
    entering_phone = State()
    confirming_profile = State()

class QuestionState(BaseState):
    """Question handling states"""
    entering_question = State()
    selecting_category = State()
    viewing_similar = State()
    awaiting_answer = State()
    rating_answer = State()

class ConsultationState(BaseState): 
    """Consultation flow states"""
    selecting_type = State()
    entering_phone = State()
    entering_description = State()
    selecting_time = State()
    confirming_details = State()
    awaiting_payment = State()
    feedback = State()

class PaymentState(BaseState):
    """Payment flow states"""
    selecting_method = State()
    awaiting_payment = State()
    confirming_payment = State()
    processing_refund = State()

class AdminState(BaseState):
    """Admin panel states"""
    viewing_dashboard = State()
    managing_users = State()
    managing_questions = State()
    managing_consultations = State()
    broadcasting = State()
    viewing_analytics = State()
    
class SupportState(BaseState):
    """Support chat states"""
    describing_issue = State()
    chatting = State()
    viewing_faq = State()
    submitting_feedback = State()

# State manager for tracking state transitions
class StateManager:
    """Manages state transitions and validation"""
    
    def __init__(self):
        self.states = {
            'user': UserState,
            'question': QuestionState,
            'consultation': ConsultationState,
            'payment': PaymentState,
            'admin': AdminState,
            'support': SupportState
        }
        
    def get_state_group(self, group_name: str) -> Optional[Type[BaseState]]:
        """Get state group by name"""
        return self.states.get(group_name)
        
    def get_state(self, group_name: str, state_name: str) -> Optional[State]:
        """Get specific state"""
        group = self.get_state_group(group_name)
        return group.get_state(state_name) if group else None
        
    async def can_transition(
        self,
        from_state: Optional[State],
        to_state: State,
        user: User
    ) -> bool:
        """Check if state transition is allowed"""
        # Always allow transition from None state
        if from_state is None:
            return True
            
        # Get state groups
        from_group = self._get_group_for_state(from_state)
        to_group = self._get_group_for_state(to_state)
        
        # Check if switching between groups
        if from_group != to_group:
            return await self._can_switch_groups(from_group, to_group, user)
            
        # Check specific state transitions
        return await self._check_transition_rules(from_state, to_state, user)
        
    def _get_group_for_state(self, state: State) -> Optional[str]:
        """Get group name for state"""
        for group_name, group_class in self.states.items():
            if state in group_class.get_state_names():
                return group_name
        return None
        
    async def _can_switch_groups(
        self,
        from_group: str,
        to_group: str,
        user: User
    ) -> bool:
        """Check if user can switch between state groups"""
        # Define allowed group transitions
        allowed_transitions = {
            'user': ['question', 'consultation', 'support'],
            'question': ['user', 'consultation'],
            'consultation': ['user', 'payment'],
            'payment': ['consultation'],
            'support': ['user'],
            'admin': ['admin']  # Admin can only transition within admin states
        }
        
        # Check if transition is allowed
        allowed = allowed_transitions.get(from_group, [])
        return to_group in allowed
        
    async def _check_transition_rules(
        self,
        from_state: State,
        to_state: State,
        user: User
    ) -> bool:
        """Check specific state transition rules"""
        # Add custom transition rules here
        return True

# Create state manager instance        
state_manager = StateManager()

__all__ = [
    'UserState',
    'QuestionState', 
    'ConsultationState',
    'PaymentState',
    'AdminState',
    'SupportState',
    'state_manager'
]