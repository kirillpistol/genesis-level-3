"""Read-only MESM source, then explicit delivery through GENESIS transport."""
import json,os,re,ssl,ssl
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler,HTTPSHandler
from .adapter import Adapter

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError("Redirects forbidden")

def local_origin(origin):
    parsed=urlsplit(origin)
    if parsed.scheme!="http" or parsed.hostname!="127.0.0.1" or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("MESM v1 integration requires explicit loopback HTTP origin")
    if not parsed.port:raise ValueError("Explicit port required")
    return origin.rstrip("/")

def decode(raw):
    def pairs(items):
        obj={}
        for k,v in items:
            if k in obj:raise ValueError("Duplicate JSON key")
            obj[k]=v
        return obj
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError("Non-finite JSON")))

class MesmClient:
    def __init__(self,origin,token,timeout=15,ca_file=None,cert_file=None,key_file=None):
        parsed=urlsplit(origin)
        if parsed.scheme=="http":self.origin=local_origin(origin)
        elif parsed.scheme=="https" and parsed.hostname and not parsed.username and not parsed.password and parsed.path in ("", "/") and not parsed.query and not parsed.fragment:
            self.origin=origin.rstrip("/")
        else:raise ValueError("Expected configured HTTPS origin or loopback test HTTP")
        if len(token)<24:raise ValueError("MESM token required")
        self.token=token;self.timeout=timeout
        context=ssl.create_default_context(cafile=ca_file)
        context.minimum_version=ssl.TLSVersion.TLSv1_2
        if bool(cert_file)!=bool(key_file):raise ValueError("Client cert/key must be supplied together")
        if cert_file:context.load_cert_chain(cert_file,key_file)
        self.opener=build_opener(ProxyHandler({}),NoRedirect(),HTTPSHandler(context=context))
    def request(self,path,query=None,html=False,body=None):
        if path not in {"/v1/health","/v1/catalog","/v1/municipalities","/v1/data","/v1/report","/v1/sources","/v1/trace","/v1/node","/v1/report-package","/v1/sessions/open","/v1/sessions/close"}:raise ValueError("Unknown source route")
        url=self.origin+path+("?"+urlencode(query) if query else "")
        raw_body=None if body is None else json.dumps(body,allow_nan=False).encode()
        req=Request(url,data=raw_body,headers={"Authorization":"Bearer "+self.token,"Content-Type":"application/json"})
        with self.opener.open(req,timeout=self.timeout) as response:
            raw=response.read(2*1024*1024+1)
            if len(raw)>2*1024*1024:raise ValueError("Source response too large")
            if html:
                if response.headers.get_content_type()!="text/html":raise ValueError("Expected HTML report")
                return raw.decode("utf-8")
            return decode(raw)
    def plans(self,municipality):
        catalog=self.request("/v1/catalog");snapshot=catalog["snapshot"]["snapshot_id"]
        dataset=next(d for d in catalog["datasets"] if d["id"]=="budget_official_plan")
        if dataset["evidence_status"]!="official_public":raise ValueError("Budget source is not declared official public")
        offset=0
        while True:
            page=self.request("/v1/data",dict(dataset="budget_official_plan",municipality=municipality,limit=100,offset=offset))
            if page["snapshot_id"]!=snapshot:raise ValueError("Snapshot changed during delivery")
            for row in page["rows"]:
                if row["municipality_name"]!=municipality:raise ValueError("Municipality mismatch")
                yield dict(contract="mesm.plan/1",municipality=municipality,year=row["year"],stage=row["stage"],unit="thousand_rub",
                           revenue=row["total_revenue"],expenditure=row["expenditure"],financing=row["financing_sources"],
                           snapshot_id=snapshot,source_url=row.get("source_url"),publication_date=row.get("publication_date"),evidence_status=dataset["evidence_status"])
            offset+=len(page["rows"])
            if offset>=page["total"]:break
            if not page["rows"]:raise ValueError("Invalid pagination")
    def save_report(self,municipality,target):
        path=Path(target);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(self.request("/v1/report",dict(municipality=municipality),html=True),encoding="utf-8")
        return path

class DevLocalCoreClient:
    """Only an explicit local test. Production uses level1_core.discovery.client_from."""
    def __init__(self):self.opener=build_opener(ProxyHandler({}),NoRedirect())
    def request(self,endpoint,path,data=None,correlation_id=None):
        endpoint=local_origin(endpoint)
        if path not in {"/v1/status","/v1/tasks","/v1/algorithms/attach"}:raise ValueError("Forbidden core route")
        headers={"Content-Type":"application/json"}
        if correlation_id:headers["X-Correlation-ID"]=correlation_id
        raw=None if data is None else json.dumps(data,allow_nan=False).encode()
        if raw and len(raw)>65536:raise ValueError("Core request too large")
        with self.opener.open(Request(endpoint+path,data=raw,headers=headers),timeout=15) as response:
            result=response.read(65537)
            if len(result)>65536:raise ValueError("Core response too large")
            return decode(result)

def deliver(source,core_client,endpoint,municipality):
    status=core_client.request(endpoint,"/v1/status")
    if status["algorithms"].get("mesm_budget")!="mesm_budget/1":raise ValueError("Attach compatible municipal module with control role first")
    adapter=Adapter(core_client,endpoint,"mesm_budget")
    results=[]
    for row in source.plans(municipality):
        correlation_id="mesm-"+row["snapshot_id"][:12]+"-"+str(row["year"])
        results.append(adapter.send(row,correlation_id=correlation_id))
    if not results:raise ValueError("No budget plan for selected municipality")
    return results
