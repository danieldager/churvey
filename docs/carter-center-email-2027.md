# Carter Center email, présidentielle 2027

Adapted 2026-08-05 from Daniel's earlier draft, which described the parked 612-question roster
instrument. Written to `~/.claude/writing-style.md`: no em dashes, no bold, plain lists, every
number with a denominator, weak parts stated rather than buried.

---

Hi Cameron,

I've collected the first set of questions and answers for the French arm of the Civic AI Audit.
647 questions with 647 answer keys, aimed at the presidential election of 18 April and 2 May
2027.

Five questions are asked once: the date of the first round, when the polls open, the
registration deadline, whether moving to another commune means re-registering, and how many
sponsorships a candidate needs. Three are asked per place: whether you need ID at the polling
station, where you register in person, and who the maire is. Those three run across a sample of
200 communes, and in Paris, Lyon and Marseille they run per arrondissement instead, since that
is where registration actually happens. It comes to 642 local questions and 5 national.

France has about 35,000 communes so we had to sample. The 200 were drawn by a rule written
before the draw and seeded so it reproduces exactly, balanced for population and for geographic
spread, and they cover all 101 departments and all 18 regions. Half of them sit either side of
1,000 inhabitants, which is the threshold where showing ID at the polling station becomes
mandatory, so that is the one question whose answer really does change from one commune to the
next. Worth knowing before reading any score off it: that question is yes or no and the sample
is 121 yes to 79 no, so a surface that always answers yes gets 60.5% while knowing nothing about
any commune. That is the number to compare against, not zero. The other two have no such floor.

Currently the data is JSON, and the fields are my guess on your schema, but I'm of course happy
to adapt it to your chosen format and fields. One thing that may need a change on your side:
French place names take articles that do not follow from the name, so Le Havre is "au Havre" in
one position and "du Havre" in another, and Angers is "d'Angers". Every commune carries both
forms as fields and the templates read those instead of the bare label. If your value set
members can hold arbitrary fields this costs nothing, and if they cannot it is a change.

After initial integration, we could have a monthly data handoff. We would update the questions
and answers on our side, and you can tell us where to drop the file. This could be done
automatically (e.g. through github). Two things make that cadence useful rather than just tidy.
The maire answers come from the interior ministry register as extracted in May, and maires do
resign between elections. And the legal populations that decide the ID answers are reissued
every January, so the ones in force for the election will not be the ones we used here. Both
want a refresh before April 2027 rather than after. We can also help build or verify the French
frontend, which should be very similar to the US one.

There is no deadline pressure this time, the election is in April 2027. One question we would
add around March 2027 is what time the polling station closes, which is 19h by default and 20h
in a lot of communes. The prefectoral orders that decide which is which are not published until
then, so it cannot be built yet, but it is the strongest local question available.

Eventually we would like to include more dynamic questions, with longer answer keys and more
involved grading. For you, the work would be the same as adding any other question, and these
would not necessarily need to fan out across all communes. You would then hand us the model
responses, and we would do the grading and analysis on our side. These are questions that would
very likely extend naturally to the US.

I'm attaching the JSON document in its current form. Here's a link to a Claude artifact that
explains the data in more detail. Happy to talk through any of it.

Best,
Daniel

---

## Optional paragraph, if the parked roster set should also be offered

Drop in after the third paragraph:

> We also have a finished set of 612 questions on who represents each department in the Senate
> and the National Assembly, and who chairs each departmental and regional council. It is built
> and checked, but it answers a different kind of question from the ones above, so I have left
> it out of this file. Say if you want it.

## What changed from the earlier draft

- 614 questions and 612 answer keys across 18 regions and 101 departments becomes 647 and 647
  across 200 communes, still covering all 101 departments and all 18 regions
- the September 27 Senate deadline is gone, the target is the presidential election of
  18 April and 2 May 2027
- added the 60.5% baseline, because without it a score on the ID question reads as much better
  than it is
- added the article and elision point, since it is the one schema change that may cost them work
- the monthly handoff paragraph now says why the cadence matters, which folds the two staleness
  risks (maires, populations) into something he was already proposing rather than listing them
  as caveats
- "all regions and departments" becomes "all communes" in the dynamic-questions paragraph

## Deliberately not in the email

- The R60 population-definition question. It was real, 168 communes nationally answer
  differently depending on which INSEE population figure the threshold means, but all of them
  were removed from the pool before drawing so no answer here depends on it. Recorded in the
  JSON under `known_limitations` for anyone who looks.
- The verification detail: 159 of 200 maires corroborated against fr.wikipedia, all 242
  addresses geocoded against the Base Adresse Nationale, one postcode corrected. It is in the
  JSON under `maire_verification`, `address_verification` and `corrections`. In the email it
  would read as defensive.
