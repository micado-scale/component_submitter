from abc import ABC, abstractmethod

class Adaptor(ABC):

    def __init__(self):
        super(Adaptor, self).__init__()

    @abstractmethod
    def translate(self):
        pass

    @abstractmethod
    def execute(self):
        pass