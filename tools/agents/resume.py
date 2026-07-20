#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re
from pathlib import Path
import checkpoint
def tid(p):
 m=re.search(r"(?m)^task_id:\s*[\"']?([^\"'\n]+)",p.read_text());return m.group(1).strip() if m else p.stem
def bundle(p):
 d=checkpoint.parse(p)
 if d is None:return {"task_id":tid(p),"checkpoint":str(p),"warning":"CHECKPOINT_MISSING","next_action":"Reconstruct and write a valid Context checkpoint from current Git, PR, CI and task evidence before substantive implementation."}
 e=checkpoint.validate(d,p)
 if e:raise ValueError("; ".join(e))
 keys=("head","branch","pr","status","proven","derived","unknown","conflicts","first_failure","changed_paths","validation","blockers","next_action")
 return {"task_id":tid(p),"checkpoint":str(p),**{k:d.get(k) for k in keys}}
def render(d):
 lines=[f"Continue task {d['task_id']} from repository state.","Do not rely on previous chat history.",f"CHECKPOINT: {d['checkpoint']}"]
 if d.get("warning"):return "\n".join(lines+[f"WARNING: {d['warning']}",f"NEXT_ACTION: {d['next_action']}","Verify live repository state before substantive implementation."])
 lines += [f"HEAD: {d.get('head','UNKNOWN')}",f"BRANCH: {d.get('branch','UNKNOWN')}",f"PR: {d.get('pr','none')}",f"STATUS: {d.get('status','UNKNOWN')}"]
 for label,key in (("PROVEN","proven"),("DERIVED","derived"),("UNKNOWN","unknown"),("CONFLICTS","conflicts"),("CHANGED_PATHS","changed_paths"),("BLOCKERS","blockers")):
  lines.append(label+":");lines += [f"- {x}" for x in d.get(key,[])]
 ff=d.get("first_failure",{})
 if isinstance(ff,dict):lines += [f"FIRST_FAILURE_MARKER: {ff.get('marker','none')}",f"FIRST_FAILURE_EVIDENCE: {ff.get('evidence','none')}"]
 lines.append("VALIDATION:")
 for x in d.get("validation",[]):
  if isinstance(x,dict):lines.append(f"- {x.get('command','')}: {x.get('result','')}; evidence={x.get('evidence','')}")
 lines += [f"NEXT_ACTION: {d.get('next_action','UNKNOWN')}","","OPERATING_RULES:","- Treat Git, checkpoint and live PR/CI as source of truth.","- Verify only live state that can invalidate NEXT_ACTION.","- Do not repeat the full preflight when checkpoint and live state agree.","- Do not rediscover PROVEN facts unless live evidence changed.","- Preserve UNKNOWN and CONFLICT; never guess.","- Do not paste full logs, diffs or old chat history.","- Execute NEXT_ACTION autonomously when safe.","- Update the checkpoint and leave exactly one next_action before handing off."]
 return "\n".join(lines)
def main():
 a=argparse.ArgumentParser();a.add_argument("--task",type=Path,required=True);a.add_argument("--json",action="store_true");x=a.parse_args();d=bundle(x.task.resolve());print(json.dumps(d,indent=2) if x.json else render(d));return 0
if __name__=="__main__":raise SystemExit(main())
