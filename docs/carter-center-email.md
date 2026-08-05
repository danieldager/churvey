# Email to the Carter Center — draft

To: Cameron [address needed], Civic AI Audit engineering
Subject: France arm of the Civic AI Audit
Attachments: carter-center-memo.md · civic_ai_audit_france_2026-08-03.json

---

Hi Cameron,

We have built a French arm of the Civic AI Audit and the data is done. 613 questions with
613 answer keys, across 18 régions and 101 départements, which is every one of them. It
should fold into what you already have as a data port rather than a fork: new value sets,
new templates, new ground truth rows, and as far as we can tell from the outside, no schema
change.

How we see it working. You tell us what format your importer takes and we adapt the data to
it. After that we handle the monthly refresh on our side and hand you the new version, and
you plug it in. Once that part is running we can also help build or verify the French
frontend, which should be close to identical to the US one.

One note on the format. A couple of our cases would be easier if value set members and
answer rows could carry an extra field. French needs a preposition per place name so the
question reads grammatically, and a small number of answers have a second name that a
grader should accept as correct. Both are in the memo.

Three of the questions are tied to the sénatoriales of 27 September. If we can be live in
time, good. If not, we are aiming at the présidentielle of 18 April 2027.

One thing we would like to try once this is running: more dynamic questions, with longer
answer keys and real grading. For you the cost is the same as adding any other question, and
these would not need to fan out across every département and région. You would hand us the
responses the models gave, and we would do the grading and keep the answer keys current on
our side.

I have attached the whole thing as one JSON file so you can look at the real questions and
answer keys before deciding anything about format. We shaped it like your own model as far
as we could read it off the public admin views, and it lists every field we added and every
place we were guessing.

The memo has the detail, including where our data is thinnest, two smaller asks about runner
location and adding Mistral Le Chat, and our reading of your data model. A sanity check on
that would be welcome.

Happy to talk through any of it.

Best,
Daniel
