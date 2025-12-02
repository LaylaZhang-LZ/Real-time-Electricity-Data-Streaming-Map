import streamlit as st
import paho.mqtt.client as mqtt
import json
import pickle
import folium
from streamlit_folium import st_folium
import time
from datetime import datetime
import pandas as pd
import threading

# Page configuration
st.set_page_config(page_title="Electricity Facility Monitor", layout="wide")

# MQTT Configuration
MQTT_BROKER = "172.17.34.107"  
MQTT_PORT = 1883
MQTT_TOPIC = "szha0285/ass2"

# Global Variables Store Data
facility_data_global = {}
last_update_global = {}
data_lock = threading.Lock()

# Load facility locations
@st.cache_data
def load_facility_locations():
    with open('facility_locations.pkl', 'rb') as f:
        return pickle.load(f)

# A function for intelligently inferring fuel types
def infer_fuel_type(facility_code, facility_info):
    """Intelligently infer the fuel type of the facility"""
    fuel_type = facility_info.get('fueltech') or facility_info.get('fuel_type')
    
    if not fuel_type or fuel_type == 'Unknown' or fuel_type == '':
        name = facility_info.get('name', '').lower()
        code = facility_code.lower()
        
        if 'wind' in name or 'wf' in code or 'wind' in code:
            return 'Wind'
        elif 'solar' in name or 'pv' in name or 'solar' in code:
            return 'Solar'
        elif 'hydro' in name or 'water' in name or 'hydro' in code:
            return 'Hydro'
        elif 'coal' in name or 'coal' in code:
            return 'Coal'
        elif 'gas' in name or 'ccgt' in code or 'ocgt' in code or 'gas' in code:
            return 'Gas'
        elif 'battery' in name or 'bess' in name or 'batt' in code:
            return 'Battery'
        elif 'biomass' in name or 'bio' in code:
            return 'Biomass'
        elif 'diesel' in name or 'distillate' in name:
            return 'Distillate'
        else:
            return 'Unknown'
    
    return fuel_type

# Initialize session state
if 'mqtt_client' not in st.session_state:
    st.session_state.mqtt_client = None
if 'mqtt_connected' not in st.session_state:
    st.session_state.mqtt_connected = False

# MQTT Callbacks
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        st.session_state.mqtt_connected = True
        client.subscribe(MQTT_TOPIC)
        print(f"✅ Connected to MQTT broker and subscribed to {MQTT_TOPIC}")
    else:
        st.session_state.mqtt_connected = False
        print(f"❌ Connection failed with code {rc}")

def on_message(client, userdata, msg):
    global facility_data_global, last_update_global
    try:
        data = json.loads(msg.payload.decode())
        
        if 'facility_code' in data:
            facility_code = data['facility_code']
            
            # Extract data from the message
            power = data.get('power_mw', 0)
            emissions = data.get('emissions_tco2e', 0)
            timestamp = data.get('event_timestamp', datetime.now().isoformat())
            hour = data.get('hour', '')
            
            # Use thread locks to protect data
            with data_lock:
                facility_data_global[facility_code] = {
                    'power': float(power) if power else 0.0,
                    'emissions': float(emissions) if emissions else 0.0,
                    'timestamp': timestamp,
                    'hour': hour
                }
                last_update_global[facility_code] = time.time()
            

            print(f"✅ {facility_code}: {power:.4f} MW, {emissions:.4f} tCO2e")
            
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
    except Exception as e:
        print(f"❌ Error processing message: {e}")
        import traceback
        traceback.print_exc()

        
# Initialize MQTT Client
def init_mqtt():
    if st.session_state.mqtt_client is None:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.on_connect = on_connect
        client.on_message = on_message
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            client.loop_start()
            st.session_state.mqtt_client = client
            time.sleep(1)
        except Exception as e:
            st.session_state.mqtt_connected = False
            st.error(f"Failed to connect to MQTT broker: {e}")

# Load facility locations
facility_locations = load_facility_locations()

# Preprocess facility data
@st.cache_data
def preprocess_facility_locations(_facility_locations):
    processed = {}
    for code, info in _facility_locations.items():
        processed_info = info.copy()
        processed_info['fuel_type'] = infer_fuel_type(code, info)
        processed[code] = processed_info
    return processed

facility_locations_processed = preprocess_facility_locations(facility_locations)

# Initialize MQTT
init_mqtt()

# Dashboard Header
st.title("🔌 Electricity Facility Monitor")
st.markdown("---")

# Copy data from a global variable
with data_lock:
    current_facility_data = facility_data_global.copy()

# Top row: Network stats
col1, col2, col3, col4 = st.columns(4)

with col1:
    if current_facility_data:
        total_power = sum(data['power'] for data in current_facility_data.values())
        st.metric("Total Power", f"{total_power:.0f} MW")
    else:
        st.metric("Total Power", "Waiting...")

with col2:
    if current_facility_data:
        total_emissions = sum(data['emissions'] for data in current_facility_data.values())
        st.metric("Total Emissions", f"{total_emissions:.0f} tCO2e")
    else:
        st.metric("Total Emissions", "Waiting...")

with col3:
    st.metric("Active Facilities", len(current_facility_data))

with col4:
    connection_status = "🟢 Connected" if st.session_state.mqtt_connected else "🔴 Disconnected"
    st.metric("MQTT Status", connection_status)

st.markdown("---")

# Control panel
col_control1, col_control2 = st.columns([1, 3])

with col_control1:
    display_mode = st.radio(
        "Display Mode:",
        ["Power Output", "Emissions"],
        key="display_mode"
    )

with col_control2:
    all_fuel_types = set()
    for facility_code, facility_info in facility_locations_processed.items():
        fuel_type = facility_info.get('fuel_type', 'Unknown')
        all_fuel_types.add(fuel_type)

    fuel_types = sorted(list(all_fuel_types))
    selected_fuel_types = st.multiselect(
        "Filter by Power Type:",
        options=fuel_types,
        default=fuel_types,
        key="fuel_filter"
    )

st.markdown("---")

# Map functions
def create_base_map():
    m = folium.Map(
        location=[-25.0, 133.0],
        zoom_start=5,
        tiles='OpenStreetMap'
    )
    return m

def get_fuel_color(fuel_type):
    color_map = {
        'Coal': 'black',
        'Gas': 'orange',
        'Hydro': 'blue',
        'Wind': 'green',
        'Solar': 'yellow',
        'Battery': 'purple',
        'Biomass': 'brown',
        'Distillate': 'red',
        'Unknown': 'gray'
    }
    return color_map.get(fuel_type, 'gray')

def get_marker_radius(power, max_power=500):
    if power <= 0:
        return 5
    normalized = min(power / max_power, 1.0)
    return 5 + (normalized * 20)

def create_dynamic_map(display_mode, selected_fuel_types, facility_data):
    m = create_base_map()
    
    max_power = 1
    if facility_data:
        powers = [data['power'] for data in facility_data.values()]
        if powers:
            max_power = max(powers)

    for facility_code, facility_info in facility_locations_processed.items():
        try:
            fuel_type = facility_info.get('fuel_type', 'Unknown')
            
            if fuel_type not in selected_fuel_types:
                continue

            lat = facility_info.get('lat')
            lng = facility_info.get('lng')
            facility_name = facility_info.get('name', facility_code)
            region = facility_info.get('network_region') or facility_info.get('region', 'Unknown')

            if lat is None or lng is None:
                continue

            color = get_fuel_color(fuel_type)

            if facility_code in facility_data:
                current_data = facility_data[facility_code]
                power = current_data['power']
                emissions = current_data['emissions']
                timestamp = current_data['timestamp']

                radius = get_marker_radius(power, max_power)

                if display_mode == "Power Output":
                    marker_label = f"{facility_name}<br>{power:.1f} MW"
                else:
                    marker_label = f"{facility_name}<br>{emissions:.1f} tCO2e"

                popup_html = f"""
                <div style="font-family: Arial; min-width: 250px;">
                    <h4 style="margin-bottom: 10px; color: #1f77b4;">{facility_name}</h4>
                    <hr style="margin: 5px 0;">
                    <p><b>Code:</b> {facility_code}</p>
                    <p><b>Type:</b> {fuel_type}</p>
                    <p><b>Region:</b> {region}</p>
                    <p><b>Power:</b> {power:.2f} MW</p>
                    <p><b>Emissions:</b> {emissions:.2f} tCO2e</p>
                    <p style="font-size: 0.9em; color: #666;"><b>Updated:</b> {timestamp[:19]}</p>
                </div>
                """

                folium.CircleMarker(
                    location=[lat, lng],
                    radius=radius,
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=marker_label,
                    color=color,
                    fill=True,
                    fillColor=color,
                    fillOpacity=0.7,
                    weight=2
                ).add_to(m)

            else:
                popup_html = f"""
                <div style="font-family: Arial; min-width: 250px;">
                    <h4 style="margin-bottom: 10px; color: #999;">{facility_name}</h4>
                    <hr style="margin: 5px 0;">
                    <p><b>Code:</b> {facility_code}</p>
                    <p><b>Type:</b> {fuel_type}</p>
                    <p><b>Region:</b> {region}</p>
                    <p style="color: #999;"><b>Status:</b> Waiting for data...</p>
                </div>
                """

                folium.CircleMarker(
                    location=[lat, lng],
                    radius=5,
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=f"{facility_name}<br>No data",
                    color='gray',
                    fill=True,
                    fillColor='lightgray',
                    fillOpacity=0.4,
                    weight=1
                ).add_to(m)

        except Exception as e:
            continue

    return m

# Display the map
if facility_locations_processed:
    with data_lock:
        facility_data_snapshot = current_facility_data.copy()
    
    map_obj = create_dynamic_map(display_mode, selected_fuel_types, facility_data_snapshot)
    st_folium(map_obj, width=1400, height=600, returned_objects=[])
else:
    st.error("No facility location data available")

# Statistics section
st.markdown("---")
st.subheader("📊 Live Statistics")

if current_facility_data:
    stats_data = []
    for facility_code, data in current_facility_data.items():
        if facility_code in facility_locations_processed:
            facility_info = facility_locations_processed[facility_code]
            fuel_type = facility_info.get('fuel_type', 'Unknown')
            if fuel_type in selected_fuel_types:
                stats_data.append({
                    'Facility': facility_info.get('name', facility_code),
                    'Code': facility_code,
                    'Type': fuel_type,
                    'Power (MW)': data['power'],
                    'Emissions (tCO2e)': data['emissions'],
                    'Last Update': data['timestamp'][:19] if isinstance(data['timestamp'], str) else str(data['timestamp'])[:19]
                })

    if stats_data:
        df = pd.DataFrame(stats_data)
        df = df.sort_values('Power (MW)', ascending=False)

        st.subheader("Top Power Producers")
        st.dataframe(df.head(20), use_container_width=True, height=400)

        st.markdown("---")
        st.subheader("Summary Statistics")
        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
        with col_stat1:
            total_power = df['Power (MW)'].sum()
            st.metric("Total Power Output", f"{total_power:.2f} MW")
        with col_stat2:
            total_emissions = df['Emissions (tCO2e)'].sum()
            st.metric("Total Emissions", f"{total_emissions:.2f} tCO2e")
        with col_stat3:
            avg_power = df['Power (MW)'].mean()
            st.metric("Average Power", f"{avg_power:.2f} MW")
        with col_stat4:
            if total_power > 0:
                emission_intensity = total_emissions / total_power
                st.metric("Emission Intensity", f"{emission_intensity:.2f} tCO2e/MW")
            else:
                st.metric("Emission Intensity", "N/A")

        st.markdown("---")
        st.subheader("Breakdown by Fuel Type")
        fuel_breakdown = df.groupby('Type').agg({
            'Power (MW)': 'sum',
            'Emissions (tCO2e)': 'sum',
            'Facility': 'count'
        }).rename(columns={'Facility': 'Count'})
        fuel_breakdown = fuel_breakdown.sort_values('Power (MW)', ascending=False)
        st.dataframe(fuel_breakdown, use_container_width=True)

    else:
        st.info("No data available for selected power types")
else:
    st.info("Waiting for data from MQTT broker...")

st.markdown("---")
col_footer1, col_footer2 = st.columns([3, 1])
with col_footer1:
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Active facilities: {len(current_facility_data)}")
with col_footer2:
    if st.button("🔄 Refresh Dashboard", use_container_width=True):
        st.rerun()