"""The scheduler: every few seconds, start the jobs that are due. Phone-call jobs go to the
Caller; everything else goes to the Expert's run_task, whose result becomes a card to tap."""
import asyncio


def make_dispatch(store, experts, dial):
    async def dispatch(job):
        expert = experts[job["expert"]]
        if job["kind"] in expert.call_kinds:
            sid = await asyncio.to_thread(dial, job["payload"]["to"], job["id"])
            store.log(expert.name, job["id"], f"calling {job['person']}")
            return {"call_sid": sid}
        card = await expert.run_task(job)
        return {"card": store.add_card(card.to_dict())} if card else {}
    return dispatch


async def tick(store, dispatch, now=None):
    """Start every due job exactly once. Returns the ids started."""
    started = []
    for job in store.due(now):
        if not store.start_job(job["id"]):
            continue
        started.append(job["id"])
        try:
            store.end_job(job["id"], True, await dispatch(job))
        except Exception as err:              # one bad job never stops the loop
            store.end_job(job["id"], False, str(err))
            store.log(job["expert"], job["id"], f"failed: {err}")
    return started


async def run_forever(store, dispatch, every=10):
    while True:
        await tick(store, dispatch)
        await asyncio.sleep(every)
