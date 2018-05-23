from abc import ABC, abstractmethod

class Adaptor(ABC):

    @abstractmethod
    def __init__(self):
        super(Adaptor, self).__init__()

    @abstractmethod
    def translate(self):
        pass

    @abstractmethod
    def execute(self):
        pass

    @abstractmethod
    def undeploy(self):
        pass

    @abstractmethod
    def cleanup(self):
        pass

    @abstractmethod
    def update(self):
        pass
