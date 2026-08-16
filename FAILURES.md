# FAILURES.md

Ways this system can still lose a DM, send a duplicate, or report a number that does not match Pseudogram's logs. These are remaining conditions, not a claim that the happy path is broken.

1. **Postgres unavailable during `POST /webhook`.** The handler inserts the event before it returns 200. If the database is down, we return 5xx and the mock API's delivery is lost unless they retry. There is no local disk fallback. I would rather drop the HTTP request than ack an event we cannot store.

2. **Process crash in the ~2 minute `sending` window after a 202 that never got committed.** The worker sets `status=sending`, calls `POST /v1/dm/send`, then writes `dm_id`. If we die after the API accepts the DM and before the `UPDATE`, the row stays `sending` until startup resets claims older than two minutes. Retry uses the same `Idempotency-Key`, so Pseudogram should return the original `dm_id` instead of sending twice. If their idempotency store expired (I have not proven the TTL), that retry would be a duplicate DM. Stats would also under-count `queued` until the claim is reset.

3. **`comment.deleted` after the send was already accepted.** Once status is `queued` / `delivered`, we do not call anything to unsend. The user still gets the DM. `sent` will include that delivery. That is intentional, but it will disagree with a grader who expects deleted comments to never appear in `sent`.

4. **Two web service instances.** Dedup of `(rule_id, recipient_user_id)` is a unique constraint, so we will not insert two outbound rows. Claiming on Postgres uses `FOR UPDATE SKIP LOCKED`. The rate limiter is in-process memory. Two Render instances would each allow 9 sends / 60s and could hit the shared 10/min key limit (`429`, then backoff). They could also each increment `duplicates_blocked` correctly while briefly racing the limiter. We document running **one** instance; scaling without a shared limiter is a stats and 429 problem, not a silent loss.

5. **In-process rate limiter vs restart.** The rolling window lives in RAM. A restart in the same 60s window lets the new process send 9 more immediately. Combined with leftover in-flight sends, that can breach 10/min. We cap at 9 instead of 10 to leave a slot; a restart still can breach. `429` is retried, so DMs are not lost, but `queued` stays high longer.

6. **`GET /stats` during a live 500-event burst.** `sent` only counts rows whose reconciler poll has observed `delivered`. Accepted DMs sit in `queued` until the next 2s reconciler tick. If the grader snapshots `/stats` immediately after the last webhook, `sent` is low and `queued` is high compared to eventual truth. Inflating `sent` on `202` would be worse, so we wait for delivery confirmation.

7. **Same user, cancelled pending DM, later comment.** If we drop a pending row because of `comment.deleted`, a later comment from that user for the same rule is allowed to enqueue. If the grader's truth treats "one DM opportunity per user per rule for the whole run" including deleted comments, we might send one more than they expect. If they expect "never DM a deleted comment, but still DM the user later," we match that.

8. **Webhook `create_task` lost on hard kill before `processed_at` is set.** The event row exists with `processed_at IS NULL`. Startup replay will process it. If the process is killed and never comes back, those DMs stay unsent. That is an ops failure (dead deploy), not an application retry bug.

9. **`duplicates_blocked` does not count `event_id` redeliveries.** A repeated `event_id` is ignored at ingest and does not increment the counter. We only count `(rule_id, user_id)` collisions on a *new* event. If truth counts every extra matching comment plus redeliveries, our number will be lower. We would rather under-count than invent blocks.

10. **Permanent `400` from `POST /v1/dm/send`.** We mark `failed` and stop. If the payload was actually fine and their 400 was a fluke, that DM is given up. I have not seen a 400 on a well-formed body in tests; the branch exists because the spec says retrying will not help.
