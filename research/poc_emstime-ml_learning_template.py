import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# Production-Ready Machine Learning Template

# ==========================================
# 1. PARSE & CLEAN HIGH-FREQUENCY DATA
# ==========================================
def load_and_preprocess_pmu_data(file_path):
    """
    Loads grid dataset, parses high-res timestamps, and handles missing steps.
    """
    # Most PMU CSVs output timestamps in ISO 8601 or raw Unix epoch nanoseconds
    df = pd.read_csv(file_path)
    
    # Adapt 'Timestamp' to the exact column name in your downloaded dataset
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
    df = df.dropna(subset=['Timestamp']).sort_values('Timestamp')
    df = df.set_index('Timestamp')
    
    # Forward-fill minor dropouts/packet loss common in time-sync networks
    df = df.ffill() 
    return df

# ==========================================
# 2. FEATURE ENGINEERING (Rolling Metrics)
# ==========================================
def engineer_features(df, target_col='Frequency', window_size=5):
    """
    Extracts statistical features that reveal clock jitter and phase slips.
    """
    # Rate of change: sudden spikes usually indicate clock steps/timing errors
    df['Delta_Value'] = df[target_col].diff().abs()
    
    # Rolling stats: capture localized variance caused by lack of sync
    df['Rolling_Mean'] = df[target_col].rolling(window=window_size).mean()
    df['Rolling_Std'] = df[target_col].rolling(window=window_size).std()
    
    # Deviation from localized normal behavior
    df['Dev_From_Mean'] = (df[target_col] - df['Rolling_Mean']).abs()
    
    # Drop rows containing NaNs resulting from rolling windows
    return df.dropna()

# ==========================================
# 3. GENERATE SIMULATED SYNCHROPHASOR DATA
# ==========================================
# (Simulating a dataset so this script runs out-of-the-box for you)
print("Generating simulated grid telemetry...")
np.random.seed(42)
n_samples = 2000

# Simulate a standard 60Hz PMU stream sampling 60 times/second
time_ticks = pd.date_range(start="2026-07-19 12:00:00", periods=n_samples, freq="16.667ms")
base_freq = 60.0 + np.random.normal(0, 0.002, n_samples)

# Inject an intentional clock-jitter anomaly (sudden artificial frequency jump)
base_freq[1200:1215] += 0.095 

mock_df = pd.DataFrame({'Timestamp': time_ticks, 'Frequency': base_freq})
mock_df.to_csv('local_grid_data.csv', index=False)

# ==========================================
# 4. TRAINING THE ML PIPELINE
# ==========================================
# Load and transform
data = load_and_preprocess_pmu_data('local_grid_data.csv')
features_df = engineer_features(data, target_col='Frequency', window_size=10)

# Select features for the ML model
feature_cols = ['Frequency', 'Delta_Value', 'Rolling_Std', 'Dev_From_Mean']
X = features_df[feature_cols]

# Scale features to prevent wide-range inputs from biasing the model
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

print("Training Isolation Forest Anomaly Detector...")
# contamination=0.01 implies we expect roughly 1% of the dataset to contain anomalies
model = IsolationForest(contamination=0.01, random_state=42, n_estimators=100)
features_df['Anomaly_Score'] = model.fit_predict(X_scaled)

: Use standard -1 for anomaly, 1 for normal
features_df['Is_Anomaly'] = np.where(features_df['Anomaly_Score'] == -1, True, False)

# ==========================================
# 5. VISUALIZE RESULTS
# ==========================================
anomalies = features_df[features_df['Is_Anomaly'] == True]
print(f"Detected {len(anomalies)} anomalous data points.")

plt.figure(figsize=(12, 5))
plt.plot(features_df.index, features_df['Frequency'], label='Grid Frequency (Hz)', color='blue', alpha=0.6)
plt.scatter(anomalies.index, anomalies['Frequency'], color='red', label='Detected Timing/Grid Anomaly', zorder=5)
plt.title("Local Grid Machine Learning Model - Anomaly Detection Loop")
plt.xlabel("Time")
plt.ylabel("Measured Value")
plt.legend()
plt.grid(True, linestyle='--', alpha=0.5)
plt.show()
