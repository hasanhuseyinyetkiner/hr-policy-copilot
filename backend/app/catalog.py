"""Static product copy served by the API."""

from app.schemas import ExamplePrompt

EXAMPLES: tuple[ExamplePrompt, ...] = (
    ExamplePrompt(
        id="leave",
        question="How many days of annual leave does a full-time employee receive?",
        blurb="Should quote the leave policy.",
    ),
    ExamplePrompt(
        id="office",
        question="How many in-office days per week are required?",
        blurb="Current sources disagree and both should be quoted.",
    ),
    ExamplePrompt(
        id="training",
        question="Within how many days must a new hire complete security awareness training?",
        blurb="Should quote the onboarding guide.",
    ),
    ExamplePrompt(
        id="meals",
        question="What is the meal reimbursement limit per day?",
        blurb="Should quote the reimbursement policy.",
    ),
    ExamplePrompt(
        id="iguana",
        question="What is the sabbatical policy for pet iguanas?",
        blurb="Nothing in the demo corpus answers this, so the app should abstain.",
    ),
)

LIMITATIONS: tuple[str, ...] = (
    "Extractive quotes only. No language model writes the answer.",
    "Not legal advice and not a compliance determination.",
    "Every stored document is synthetic demo material.",
    "There is no authentication. The audience field is a retrieval filter, not access control.",
    "A paraphrase that shares fewer than three content words with the policies can abstain.",
    "Contradiction detection only flags differing in-office day numbers.",
)

EMBEDDING_LICENSE = "Apache-2.0"
