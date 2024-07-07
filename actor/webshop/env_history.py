from typing import List, Dict
from langchain.memory import ChatMessageHistory

class EnvironmentHistory:
    def __init__(self, base_query: str) -> None:
        self._cur_query: str = base_query
        # self._history: List[Dict[str, str]] = history
        self._last_action: str = ''
        self._is_exhausted: bool = False
        self.reset()
        

    def add(self, label: str, value: str) -> None:
        assert label in ['action', 'observation', 'human_edit']
        if label == 'action':
            if value == self._last_action:
                self._is_exhausted = True
            else:
                self._last_action = value
            self._history.add_ai_message(value)
        elif label == 'observation':
            self._history.add_user_message(value)

    def check_is_exhausted(self) -> bool:
        return self._is_exhausted

    def reset(self) -> None:
        self._history = ChatMessageHistory()
        self._history.add_user_message(self._cur_query)

    @property
    def messages(self) -> list:
        return self._history.messages
  
    def add_new_task(self, start_info: str, memory: List[str]) -> str:
        query = "Now, you need to perform a new task."
        # add memory if it exists
        if len(memory) > 0:
            if memory:
                query += '\n\nYou have attempted to complete this task before and failed.'
                feedback_str = "\n- ".join([f.strip() for f in memory])
                query += f"The following feedback(s) is given by the user based on your previous trial. Use them to improve your strategy of correctly fulfill the user's instruction. Feedbacks:\n- {feedback_str}"
        query += f"\nThe task is:\nObservation:\n{start_info}"
        self._history.add_user_message(query)

