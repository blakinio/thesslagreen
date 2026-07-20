#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re,sys
from pathlib import Path
H="## Context checkpoint";L={"context_routes","owned_paths","proven","derived","unknown","conflicts","rejected_hypotheses","changed_paths","blockers"};P={"","none","unknown","pending","n/a","tbd","todo","later"}
def cfg():return json.loads((Path(__file__).resolve().parents[2]/"docs/agents/GOVERNANCE_CONTRACT.json").read_text())["shared_checkpoint_contract"]
def s(v):
 v=v.strip();return v[1:-1] if len(v)>=2 and v[0]==v[-1] and v[0] in {'\"',"'"} else v
def parse(p):
 t=p.read_text();m=list(re.finditer(r"(?m)^## Context checkpoint\s*$",t))
 if not m:return None
 if len(m)!=1:raise ValueError(f"{p}: expected one {H}")
 r=t[m[0].end():];n=re.search(r"(?m)^##\s+",r);q=r[:n.start()] if n else r;f=re.search(r"```(?:yaml|yml)\s*\n",q,re.I)
 if not f:raise ValueError(f"{p}: checkpoint has no YAML fence")
 e=q.find("```",f.end());d={};cur=None;cv=None
 if e<0:raise ValueError(f"{p}: checkpoint fence not closed")
 for no,raw in enumerate(q[f.end():e].splitlines(),1):
  if not raw.strip() or raw.lstrip().startswith("#"):continue
  ind=len(raw)-len(raw.lstrip());line=raw.strip()
  if ind==0:
   if ":" not in line:raise ValueError(f"{p}:{no}: invalid line")
   k,v=line.split(":",1);k=k.strip();v=v.strip();cur=k;cv=None
   if k in d:raise ValueError(f"{p}:{no}: duplicate {k}")
   if k in L or k=="validation":d[k]=[] if v in {"","[]"} else (_ for _ in ()).throw(ValueError(f"{p}:{no}: {k} must be list"))
   elif k=="first_failure":d[k]={}
   else:d[k]=s(v)
  elif cur in L:d[cur].append(s(line[2:])) if ind==2 and line.startswith("- ") else (_ for _ in ()).throw(ValueError(f"{p}:{no}: invalid list"))
  elif cur=="first_failure":k,v=line.split(":",1);d[cur][k.strip()]=s(v)
  elif cur=="validation":
   if ind==2 and line.startswith("- "):k,v=line[2:].split(":",1);cv={k.strip():s(v)};d[cur].append(cv)
   elif ind==4 and cv is not None:k,v=line.split(":",1);cv[k.strip()]=s(v)
   else:raise ValueError(f"{p}:{no}: invalid validation")
 return d
def validate(d,p):
 c=cfg();e=[]
 for k in c["required_fields"]:
  if k not in d:e.append(f"{p}: missing {k}")
 if str(d.get("checkpoint_version",""))!=str(c["version"]):e.append(f"{p}: wrong checkpoint_version")
 if d.get("status") not in c["allowed_statuses"]:e.append(f"{p}: unsupported status")
 if str(d.get("next_action","")).strip().casefold() in P:e.append(f"{p}: next_action must be concrete")
 ff=d.get("first_failure")
 if not isinstance(ff,dict) or not all(str(ff.get(k,"")).strip() for k in ("marker","evidence")):e.append(f"{p}: invalid first_failure")
 for k,limit in c.get("compactness_limits",{}).items():
  v=d.get(k,[])
  if not isinstance(v,list):e.append(f"{p}: {k} must be list")
  elif len(v)>limit:e.append(f"{p}: {k} compactness limit {limit} exceeded")
 val=d.get("validation",[])
 for i,x in enumerate(val,1):
  if not isinstance(x,dict) or not all(str(x.get(k,"")).strip() for k in ("command","result","evidence")):e.append(f"{p}: invalid validation {i}")
  elif x["result"] not in c["allowed_validation_results"]:e.append(f"{p}: unsupported validation result")
 fields=list(c["evidence_state_fields"].values());sets={k:{" ".join(str(x).casefold().split()) for x in d.get(k,[]) if str(x).strip()} for k in fields}
 for i,a in enumerate(fields):
  for b in fields[i+1:]:
   if sets[a]&sets[b]:e.append(f"{p}: evidence overlaps {a}/{b}")
 return e
def main():
 a=argparse.ArgumentParser();a.add_argument("task",nargs="?",type=Path);a.add_argument("--tasks",type=Path);a.add_argument("--require-checkpoint",action="store_true");x=a.parse_args()
 if bool(x.task)==bool(x.tasks):a.error("provide one task or --tasks")
 ps=[x.task] if x.task else sorted(x.tasks.glob("*.md"));err=[]
 for p in ps:
  try:d=parse(p)
  except Exception as z:err.append(str(z));continue
  if d is None:
   if x.require_checkpoint:err.append(f"{p}: missing {H}")
  else:err+=validate(d,p)
 for z in err:print("ERROR:",z,file=sys.stderr)
 return 1 if err else (print(f"Validated {len(ps)} checkpoint task(s).") or 0)
if __name__=="__main__":raise SystemExit(main())
