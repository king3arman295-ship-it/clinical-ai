from collections import defaultdict


class ConversationMemory:
    """
    Stores conversation history for each session.

    Current implementation:
        - In-memory storage

    Future implementations:
        - Redis
        - PostgreSQL
        - MongoDB
    """

    def __init__(self):
        self._memory = defaultdict(list)

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ):
        """
        Add a message to the conversation.
        """

        self._memory[session_id].append(
            {
                "role": role,
                "content": content,
            }
        )

    def get_messages(
        self,
        session_id: str,
    ) -> list:
        """
        Return the conversation history.
        """

        return self._memory.get(
            session_id,
            [],
        )

    def clear(
        self,
        session_id: str,
    ):
        """
        Clear a conversation.
        """

        self._memory.pop(
            session_id,
            None,
        )

    def has_session(
        self,
        session_id: str,
    ) -> bool:
        """
        Check whether a session exists.
        """

        return session_id in self._memory

    def remove_last_message(
        self,
        session_id: str,
    ):
        """
        Remove the last message from a conversation.
        """

        if (
            session_id in self._memory
            and self._memory[session_id]
        ):
            self._memory[session_id].pop()

    def total_messages(
        self,
        session_id: str,
    ) -> int:
        """
        Return the number of messages in a conversation.
        """

        return len(
            self._memory.get(
                session_id,
                [],
            )
        )

    def all_sessions(self):
        """
        Return every active session.
        """

        return list(
            self._memory.keys()
        )