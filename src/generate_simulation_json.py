import pandas as pd
import numpy as np
import json
import os

def generate_json():
    # Dynamically resolve project directory relative to the script location (src/generate_simulation_json.py)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    outputs_dir = os.path.join(project_dir, 'outputs')
    app_data_dir = os.path.join(project_dir, 'app', 'data')
    os.makedirs(app_data_dir, exist_ok=True)
    
    # Paths
    acn_sim_path = os.path.join(outputs_dir, 'acn_simulation_results.csv')
    acn_metrics_path = os.path.join(outputs_dir, 'acn_metrics.csv')
    uev_sim_path = os.path.join(outputs_dir, 'urbanev_simulation_results.csv')
    uev_metrics_path = os.path.join(outputs_dir, 'urbanev_metrics.csv')
    
    results = {}
    
    # -----------------------------
    # 1. PROCESS ACN
    # -----------------------------
    if os.path.exists(acn_sim_path) and os.path.exists(acn_metrics_path):
        print("Processing ACN...")
        acn_sim = pd.read_csv(acn_sim_path)
        acn_metrics = pd.read_csv(acn_metrics_path).iloc[0].to_dict()
        
        acn_sim['timestamp'] = pd.to_datetime(acn_sim['timestamp'])
        acn_sim['date'] = acn_sim['timestamp'].dt.date
        
        # Test profiles (24 hours)
        acn_hourly = acn_sim.groupby('hour').agg({
            'occupancy': 'mean',
            'dynamic_occupancy': 'mean',
            'charging_load_kW': 'mean',
            'dynamic_volume': 'mean',
            'dynamic_price': 'mean'
        }).reset_index().sort_values('hour')
        
        # Daily feedback simulation
        # Mimic the MonitoringLearningAgent and TariffPricingAgent daily feedback loop
        # We group the test dataset by day
        days = sorted(acn_sim['date'].unique())
        feedback_list = []
        current_elasticity = 0.25
        max_occ_acn = acn_sim['occupancy'].max()
        cap_acn = max_occ_acn * 1.1 if max_occ_acn > 0 else 1.0
        
        for d in days:
            day_df = acn_sim[acn_sim['date'] == d]
            if len(day_df) < 12: # Skip partial days
                continue
                
            # Compute daily metrics
            base_vol = day_df['charging_load_kW']
            dyn_vol = day_df['dynamic_volume']
            occ_base = day_df['occupancy']
            occ_dyn = day_df['dynamic_occupancy']
            p_dyn = day_df['dynamic_price']
            
            rev_base = np.sum(base_vol * 15.0)
            rev_dyn = np.sum(dyn_vol * p_dyn)
            rev_gain = ((rev_dyn - rev_base) / max(1.0, rev_base)) * 100.0
            
            queue_base = np.maximum(0.0, occ_base - cap_acn)
            queue_dyn = np.maximum(0.0, occ_dyn - cap_acn)
            avg_q_base = np.mean(queue_base)
            avg_q_dyn = np.mean(queue_dyn)
            queue_red = ((avg_q_base - avg_q_dyn) / max(0.1, avg_q_base)) * 100.0 if avg_q_base > 0 else 0.0
            
            off_peak_mask = (occ_base / cap_acn) < 0.3
            vol_base_offpeak = np.sum(base_vol[off_peak_mask])
            vol_dyn_offpeak = np.sum(dyn_vol[off_peak_mask])
            off_peak_uplift = ((vol_dyn_offpeak - vol_base_offpeak) / max(1.0, vol_base_offpeak)) * 100.0 if vol_base_offpeak > 0 else 0.0
            
            feedback_list.append({
                "day": str(d),
                "elasticity": float(current_elasticity),
                "revenue_gain_pct": float(rev_gain),
                "queue_reduction_pct": float(queue_red),
                "off_peak_uplift_pct": float(off_peak_uplift)
            })
            
            # Monitoring Agent update logic
            new_elasticity = current_elasticity
            if off_peak_uplift < 5.0 and np.mean(occ_base / cap_acn) < 0.2:
                new_elasticity += 0.05
            if avg_q_dyn > 0.5:
                new_elasticity += 0.05
            if rev_gain < -10.0:
                new_elasticity -= 0.10
            current_elasticity = max(0.05, min(0.6, new_elasticity))
            
        results['acn'] = {
            "metrics": acn_metrics,
            "feedback": feedback_list,
            "train_metrics": {
                "occupancy": {"RMSE": 2.9083, "MAE": 2.0653, "R2": 0.9524},
                "volume": {"RMSE": 10.7583, "MAE": 7.4174, "R2": 0.8057}
            },
            "daily_profile_base_occ": acn_hourly['occupancy'].tolist(), # proxy using test profile
            "daily_profile_base_vol": acn_hourly['charging_load_kW'].tolist(), # proxy using test profile
            "test_profile_base_occ": acn_hourly['occupancy'].tolist(),
            "test_profile_dyn_occ": acn_hourly['dynamic_occupancy'].tolist(),
            "test_profile_base_vol": acn_hourly['charging_load_kW'].tolist(),
            "test_profile_dyn_vol": acn_hourly['dynamic_volume'].tolist(),
            "test_profile_dyn_price": acn_hourly['dynamic_price'].tolist()
        }
        
    # -----------------------------
    # 2. PROCESS URBANEV
    # -----------------------------
    if os.path.exists(uev_sim_path) and os.path.exists(uev_metrics_path):
        print("Processing UrbanEV...")
        uev_sim = pd.read_csv(uev_sim_path)
        uev_metrics = pd.read_csv(uev_metrics_path).iloc[0].to_dict()
        
        uev_sim['timestamp'] = pd.to_datetime(uev_sim['timestamp'])
        uev_sim['date'] = uev_sim['timestamp'].dt.date
        
        # Test profiles (24 hours)
        uev_hourly = uev_sim.groupby('hour').agg({
            'occupancy': 'mean',
            'dynamic_occupancy': 'mean',
            'volume': 'mean',
            'dynamic_volume': 'mean',
            'dynamic_price': 'mean'
        }).reset_index().sort_values('hour')
        
        # Daily feedback simulation
        days = sorted(uev_sim['date'].unique())
        feedback_list = []
        current_elasticity = 0.25
        
        for d in days:
            day_df = uev_sim[uev_sim['date'] == d]
            if len(day_df) < 12:
                continue
                
            # Compute daily metrics
            base_vol = day_df['volume']
            dyn_vol = day_df['dynamic_volume']
            occ_base = day_df['occupancy']
            occ_dyn = day_df['dynamic_occupancy']
            p_dyn = day_df['dynamic_price']
            cap_uev = day_df['capacity']
            
            rev_base = np.sum(base_vol * 15.0)
            rev_dyn = np.sum(dyn_vol * p_dyn)
            rev_gain = ((rev_dyn - rev_base) / max(1.0, rev_base)) * 100.0
            
            queue_base = np.maximum(0.0, occ_base - cap_uev)
            queue_dyn = np.maximum(0.0, occ_dyn - cap_uev)
            avg_q_base = np.mean(queue_base)
            avg_q_dyn = np.mean(queue_dyn)
            queue_red = ((avg_q_base - avg_q_dyn) / max(0.1, avg_q_base)) * 100.0 if avg_q_base > 0 else 0.0
            
            off_peak_mask = (occ_base / cap_uev) < 0.3
            vol_base_offpeak = np.sum(base_vol[off_peak_mask])
            vol_dyn_offpeak = np.sum(dyn_vol[off_peak_mask])
            off_peak_uplift = ((vol_dyn_offpeak - vol_base_offpeak) / max(1.0, vol_base_offpeak)) * 100.0 if vol_base_offpeak > 0 else 0.0
            
            feedback_list.append({
                "day": str(d),
                "elasticity": float(current_elasticity),
                "revenue_gain_pct": float(rev_gain),
                "queue_reduction_pct": float(queue_red),
                "off_peak_uplift_pct": float(off_peak_uplift)
            })
            
            # Monitoring Agent update logic
            new_elasticity = current_elasticity
            if off_peak_uplift < 5.0 and np.mean(occ_base / cap_uev) < 0.2:
                new_elasticity += 0.05
            if avg_q_dyn > 0.5:
                new_elasticity += 0.05
            if rev_gain < -10.0:
                new_elasticity -= 0.10
            current_elasticity = max(0.05, min(0.6, new_elasticity))
            
        results['urbanev'] = {
            "metrics": uev_metrics,
            "feedback": feedback_list,
            "train_metrics": {
                "occupancy": {"RMSE": 2.7092, "MAE": 1.5467, "R2": 0.9868},
                "volume": {"RMSE": 218.6360, "MAE": 71.8344, "R2": 0.9107}
            },
            "daily_profile_base_occ": uev_hourly['occupancy'].tolist(),
            "daily_profile_base_vol": uev_hourly['volume'].tolist(),
            "test_profile_base_occ": uev_hourly['occupancy'].tolist(),
            "test_profile_dyn_occ": uev_hourly['dynamic_occupancy'].tolist(),
            "test_profile_base_vol": uev_hourly['volume'].tolist(),
            "test_profile_dyn_vol": uev_hourly['dynamic_volume'].tolist(),
            "test_profile_dyn_price": uev_hourly['dynamic_price'].tolist()
        }
        
    # Write JSON output
    out_json_path = os.path.join(app_data_dir, 'simulation_results.json')
    with open(out_json_path, 'w') as f:
        json.dump(results, f, indent=4)
    print(f"Successfully wrote freshly generated JSON to: {out_json_path}")

if __name__ == '__main__':
    generate_json()
