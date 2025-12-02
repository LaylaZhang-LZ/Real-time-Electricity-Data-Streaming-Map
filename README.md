Electricity Facility Monitor
============================

Installation
------------
    pip install -r requirements.txt


Running the Dashborad
---------------
1. Set your API key

2. Run 'Tasks1-3.ipynb' in Jupyter. 
    You will get:
    - Facility location data (facility_location.pkl)
    - Facility data (nem_facility_data.csv)
    - Market data (nem_market_data.csv)
    - The data will be published (Default Broker is "172.17.34.107")

3. Run 'Task4-5.py' in the terminal. 
    The following command can be used:
       streamlit run Task4-5.py

4. Your browser should open automatically
<img width="1633" height="1204" alt="image" src="https://github.com/user-attachments/assets/2be73d3b-0b4e-4c92-a163-12e19148a129" />


Directory Layout after running
--------------------------
project/
├── Tasks1-3.ipynb
├── Task4-5.py
├── facility_locations.pkl                      # Auto-generated 
├── requirements.txt
├── README.txt 
└── nem_data_output/
        ├── nem_facility_data.csv            # Auto-generated 
        └── nem_market_data.csv           # Auto-generated 

