from contextlib import asynccontextmanager

class MockDBSession:
    async def __aenter__(self):
        print("ℹ️ [MockDB] Acquired mock database session.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        print("ℹ️ [MockDB] Released mock database session.")

    def get(self, *args, **kwargs):
        return None

    def add(self, *args, **kwargs):
        pass
    
    async def commit(self):
        pass

class MockDBSessionMaker:
    @asynccontextmanager
    async def __call__(self):
        session = MockDBSession()
        try:
            yield session
        finally:
            pass

