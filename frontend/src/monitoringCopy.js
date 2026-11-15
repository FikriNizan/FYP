export const monitoringCopy = [
  'An observed outcome is a volume drop: the next three-month average combined flow is at or below half of a positive trailing twelve-month average. It does not mean account closure. Unavailable includes outcomes not imported or incomplete source coverage. It is never counted as a zero or a negative outcome.',
  'Outcomes exist only after an explicit administrator import after the full three-month window. This page does not create labels from later assessments.',
  'Predicted and observed rates use the same customers when compared. Brier is a probability-error score; lower is better, but it does not alone prove calibration. The same-group constant reference retrospectively predicts that group\'s observed rate for everyone. It is a descriptive yardstick, not a frozen forward benchmark or a universal pass mark.',
  'Documented delivery means a completed RM visit, customer contact or service fix dated inside the outcome window. Planned work, attempts and notes are excluded. No recorded delivery does not prove that nothing happened. These groups are selected, not controlled; differences do not prove retention benefit.',
  'Input and risk movement compares the selected assessment with an earlier batch under the same frozen protocol. It is descriptive only; no alert threshold or causal explanation is assigned.',
];

export const classificationCopy = {
  precision:'Of the flagged customers, how many had an observed volume drop?',
  recall:'Of all observed volume drops, how many were flagged?',
  f1:'A balanced summary of precision and recall, shown as a 0–1 score.',
};
