import modelParams from "./model.json";

export interface PredictionResult {
  home_win_probability: number;
  away_win_probability: number;
  overtime_probability: number;
  predicted_home_score: number;
  predicted_away_score: number;
  confidence: number;
  model: string;
}

export function predict(features: number[]): PredictionResult | null {
  try {
    const { scaler_mean, scaler_scale, coef, intercept } = modelParams;

    // StandardScaler: (X - mean) / scale
    const scaled = features.map((x, i) => {
      const mean = scaler_mean[i];
      const scale = scaler_scale[i];
      return scale > 0 ? (x - mean) / scale : 0;
    });

    // Logistic regression: z = sum(scaled[i] * coef[i]) + intercept
    let z = intercept;
    for (let i = 0; i < scaled.length; i++) {
      z += scaled[i] * coef[i];
    }

    // Sigmoid
    const homeProb = 1 / (1 + Math.exp(-z));
    const awayProb = 1 - homeProb;

    const expectedTotal = 5.8;
    const expectedSpread = (homeProb - awayProb) * expectedTotal * 2;
    const homeScore = Math.max(0, Math.round(((expectedTotal + expectedSpread) / 2) * 100) / 100);
    const awayScore = Math.max(0, Math.round(((expectedTotal - expectedSpread) / 2) * 100) / 100);
    const spread = Math.abs(homeScore - awayScore);
    const otProb = spread < 0.7 ? 0.28 : spread < 1.2 ? 0.18 : 0.10;
    const confidence = Math.min(0.95, 0.50 + Math.abs(homeProb - 0.5) * 1.5);

    return {
      home_win_probability: Math.round(homeProb * 10000) / 10000,
      away_win_probability: Math.round(awayProb * 10000) / 10000,
      overtime_probability: Math.round(otProb * 10000) / 10000,
      predicted_home_score: homeScore,
      predicted_away_score: awayScore,
      confidence: Math.round(confidence * 10000) / 10000,
      model: "LogisticRegression",
    };
  } catch (e) {
    console.error("Prediction failed:", e);
    return null;
  }
}
