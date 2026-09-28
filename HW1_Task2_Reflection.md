# Homework 1 — Task 2: Reflection

On 22 September 2026, within the ten days before this submission, OpenAI released
GPT-6 Sol and GPT-6 Luna. Its announcement advertised roughly halved API prices
relative to the previous generation's promotional pricing. OpenAI also reported
that Sol made about half as many factual mistakes as its predecessor on an
internal evaluation. That is a company-reported result on selected conversations,
not a guarantee about every real-world task. [1]

I nearly skipped the article. New model names come out constantly and I had mostly
stopped keeping track. What made me stop this time was the emphasis on making
everyday work cheaper to automate. Document processing and routine analysis are
not just benchmark tasks to me; they are parts of the jobs I might apply for.

I used to follow AI news by asking how capable the models were getting. I don't think
that's the only useful question anymore. Lower API prices could make more tasks
economical to automate. They do not mean that doing a person's entire job suddenly
costs half as much: integration, supervision, error correction and accountability
also cost money. Still, the announcement shifted my attention from capability
alone to the cost of producing a dependable result.

That is uncomfortable to sit with in finance specifically. Administrative and
clerical tasks are part of many financial workflows. As background to the September
announcement, Bloomberg reported on 1 July that US financial-activities and
information-sector payrolls had fallen by about 28,000 jobs per month on average
in 2026 through May. That is not evidence that AI caused every lost job. [2]
A Stanford study, revised in August, found employment declines concentrated in
occupations where AI primarily substitutes for human tasks, with particularly
concerning patterns among younger workers. The authors explicitly describe these
as early descriptive indicators, not causal estimates. [3] These earlier reports
provide context for my reaction to the recent launch, rather than additional
events from the assignment's ten-day window.

I came into this programme assuming that if I got good enough at the analysis itself,
I would be fine. I am less sure about that now. Being good at something a model does
acceptably for a fraction of the cost does not feel like a strong place to stand.

The part that seems more durable is the other half of the work: being able to tell
whether an answer is actually right.

Task 1 of this assignment made that concrete for me. Getting the model to read a
receipt was only the starting point. A misread number could still produce an
ordinary-looking total. The implementation therefore reads each receipt in two
different ways, compares the extracted amounts, and performs the arithmetic in
Python. Testing then exposed a separate problem: an earlier incorrect payment
could win a voting tie against a later, reconciled reading. Fixing that selection
rule showed me that errors can come from the surrounding software as well as the
model. Even agreement between two readings is evidence of consistency, not proof
of correctness; both can make the same mistake.

I think this need for verification extends beyond this assignment.

So in practical terms, I would rather aim coursework and internships at validation and
model risk than at pure execution. In my next project, I want to keep a labelled
evaluation set, record failure cases, and measure error rates alongside API cost.
For internships, I will look for opportunities involving model validation, data
quality or financial controls, while continuing to develop the financial knowledge
needed to judge the outputs. I realise verification can be automated too. My aim
is therefore to learn how to decide what evidence is sufficient, when a result
needs human review, and who is responsible if it is wrong.

---

## Sources

1. OpenAI, [*Introducing GPT-6 Sol and Luna*](https://openai.com/index/introducing-gpt-6-sol-and-luna/), 22 September 2026.
2. Matthew Boesler / Bloomberg News, [*Two Sectors Losing 28,000 Jobs Monthly Show AI Impact on Labor*](https://news.bloomberglaw.com/daily-labor-report/two-sectors-losing-28-000-jobs-monthly-show-ai-impact-on-labor), 1 July 2026.
3. Erik Brynjolfsson, Bharat Chandar and Ruyu Chen, [*Canaries in the Coal Mine? Six Facts about the Recent Employment Effects of Artificial Intelligence*](https://digitaleconomy.stanford.edu/publication/canaries-in-the-coal-mine-six-facts-about-the-recent-employment-effects-of-artificial-intelligence/), revised 12 August 2026.
