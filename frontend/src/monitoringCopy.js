export const monitoringCopy = [
  'An observed outcome is a volume drop: the next three-month average combined flow is at or below half of a positive trailing twelve-month average. It does not mean account closure. Unavailable includes outcomes not imported or incomplete source coverage. It is never counted as a zero or a negative outcome.',
  'Outcomes are derived automatically when the monthly package that completes an assessment\'s three-month window is uploaded, from the uploaded packages\' own data. A month that is not yet uploaded leaves the assessment waiting; nothing is guessed. An administrator can also load outcomes from the trusted research file with the command below.',
  'Predicted and observed figures use the same customers when compared. Expected drops are the sum of predicted risk. The Brier score (a probability-error score) remains in the API and documentation; it is not shown on screen.',
  'Documented delivery means a completed RM visit, customer contact or service fix dated inside the outcome window. Planned work, attempts and notes are excluded. No recorded delivery does not prove that nothing happened. These groups are selected, not controlled; differences do not prove retention benefit.',
  'Input and risk movement compares the selected assessment with an earlier batch under the same frozen protocol. It is descriptive only; no alert threshold or causal explanation is assigned.',
];

export const classificationCopy = {
  precision:'Of the flagged customers, how many had an observed volume drop?',
  recall:'Of all observed volume drops, how many were flagged?',
  f1:'A balanced summary of precision and recall, shown as a 0–1 score.',
};
