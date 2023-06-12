# This is for testing purposes only.

class InMemoryDatabase(object):
    def __init__(self):
        self.data = {
            1: []
        }

    @property
    def insert(self):
        return self.data

    @property
    def get(self):
        return self.data
