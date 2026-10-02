"""Adapter delegates transport to level 1. No automatic task retries."""
class Adapter:
    def __init__(self,client,endpoint,algorithm):
        self.client,self.endpoint,self.algorithm=client,endpoint,algorithm
    def send(self,record):
        return self.client.request(self.endpoint,'/v1/tasks',
                {'api_version':'1.0','algorithm':self.algorithm,'data':record})
    def stream(self,records):
        for record in records:
            yield self.send(record)
