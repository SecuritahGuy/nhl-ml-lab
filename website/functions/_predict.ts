import { MODEL_PARAMS } from "./_model";

export interface PredictionResult {
  home_win_probability: number;
  away_win_probability: number;
  overtime_probability: number;
  predicted_home_score: number;
  predicted_away_score: number;
  confidence: number;
  model: string;
}

function logisticPredict(scaled: number[], coef: number[], intercept: number): number {
  let z = intercept;
  for (let i = 0; i < scaled.length; i++) {
    z += scaled[i] * coef[i];
  }
  return 1 / (1 + Math.exp(-z));
}

function logisticLogOdds(scaled: number[], coef: number[], intercept: number): number {
  let z = intercept;
  for (let i = 0; i < scaled.length; i++) {
    z += scaled[i] * coef[i];
  }
  return z;
}

function scoreProbs(homeProb: number): {
  home_score: number; away_score: number; ot_prob: number; confidence: number;
} {
  const awayProb = 1 - homeProb;
  const expectedTotal = 5.8;
  const expectedSpread = (homeProb - awayProb) * expectedTotal * 2;
  const homeScore = Math.max(0, Math.round(((expectedTotal + expectedSpread) / 2) * 100) / 100);
  const awayScore = Math.max(0, Math.round(((expectedTotal - expectedSpread) / 2) * 100) / 100);
  const spread = Math.abs(homeScore - awayScore);
  const otProb = spread < 0.7 ? 0.28 : spread < 1.2 ? 0.18 : 0.10;
  const confidence = Math.min(0.95, 0.50 + Math.abs(homeProb - 0.5) * 1.5);
  return { home_score: homeScore, away_score: awayScore, ot_prob: otProb, confidence };
}

export function predict(features: number[]): PredictionResult | null {
  try {
    const { scaler_mean, scaler_scale, ensemble_coefs, ensemble_biases,
            coef, intercept, type } = MODEL_PARAMS;

    const scaled = features.map((x, i) => {
      const mean = scaler_mean[i];
      const scale = scaler_scale[i];
      return scale > 0 ? (x - mean) / scale : 0;
    });

    let homeProb: number;
    let modelName: string;

    if (ensemble_coefs && ensemble_biases) {
      let totalLogit = 0;
      const n = ensemble_coefs.length;
      for (let m = 0; m < n; m++) {
        totalLogit += logisticLogOdds(scaled, ensemble_coefs[m], ensemble_biases[m]);
      }
      homeProb = 1 / (1 + Math.exp(-totalLogit / n));
      modelName = "MLX-Ensemble-5";
    } else if (coef) {
      homeProb = logisticPredict(scaled, coef, intercept ?? 0);
      modelName = type ?? "MLX-LR";
    } else {
      return null;
    }

    const awayProb = 1 - homeProb;
    const { home_score, away_score, ot_prob, confidence } = scoreProbs(homeProb);

    return {
      home_win_probability: Math.round(homeProb * 10000) / 10000,
      away_win_probability: Math.round(awayProb * 10000) / 10000,
      overtime_probability: Math.round(ot_prob * 10000) / 10000,
      predicted_home_score: home_score,
      predicted_away_score: away_score,
      confidence: Math.round(confidence * 10000) / 10000,
      model: modelName,
    };
  } catch (e) {
    console.error("Prediction failed:", e);
    return null;
  }
}
