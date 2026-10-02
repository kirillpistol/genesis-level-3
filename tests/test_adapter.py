import unittest
from level3_data.adapter import Adapter
class AdapterTests(unittest.TestCase):
    def test_sequential(self):
        class Client:
            def __init__(self):self.messages=[]
            def request(self,endpoint,path,body):
                self.messages.append((endpoint,path,body));return {'result':body['data']}
        client=Client()
        result=list(Adapter(client,'https://localhost:8080','numeric').stream([1,2]))
        self.assertEqual(result,[{'result':1},{'result':2}])
        self.assertEqual(client.messages[0][2]['api_version'],'1.0')
    def test_no_retry(self):
        class Client:
            def request(self,*args):raise TimeoutError()
        with self.assertRaises(TimeoutError):Adapter(Client(),'https://localhost','numeric').send(1)

    def test_correlation_propagation(self):
        class Client:
            def request(self,*args,**kwargs):return kwargs
        result=Adapter(Client(),'https://localhost','numeric').send(1,correlation_id='source-123')
        self.assertEqual(result,{'correlation_id':'source-123'})
