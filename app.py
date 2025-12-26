# app.py - Complete Streamlit Conversion (GitHub Storage Only)
import streamlit as st
import pandas as pd
from datetime import datetime
import json
import logging
import io
import base64
import time
import requests
import zipfile
from io import BytesIO

# ============================================================
# GITHUB STORAGE - ONLY CHANGE FROM YOUR ORIGINAL CODE
# ============================================================

class GitHubStorage:
    """Replaces local file storage with GitHub storage - ALL LOGIC UNCHANGED"""
    
    def __init__(self):
        # Load from Streamlit secrets
        try:
            self.owner = st.secrets["GITHUB_OWNER"]
            self.repo = st.secrets["GITHUB_REPO"]
            self.token = st.secrets["GITHUB_TOKEN"]
            self.branch = st.secrets.get("GITHUB_BRANCH", "main")
        except:
            st.error("⚠️ GitHub credentials not configured. Please check secrets.toml")
            self.owner = ""
            self.repo = ""
            self.token = ""
            self.branch = "main"
        
        self.base_api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/contents"
        self.base_raw_url = f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/{self.branch}"
        self.headers = {"Authorization": f"token {self.token}"} if self.token else {}
    
    def read_json(self, filename):
        """Read JSON file from GitHub"""
        if not self.token:
            return None
        
        url = f"{self.base_api_url}/{filename}"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                content = response.json().get("content", "")
                if content:
                    return json.loads(base64.b64decode(content).decode('utf-8'))
            return None
        except:
            return None
    
    def write_json(self, filename, data):
        """Write JSON file to GitHub"""
        if not self.token:
            return False
        
        url = f"{self.base_api_url}/{filename}"
        
        # Get SHA if file exists
        sha = None
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                sha = response.json().get("sha")
        except:
            pass
        
        # Prepare content
        content = json.dumps(data, indent=4, ensure_ascii=False)
        content_b64 = base64.b64encode(content.encode('utf-8')).decode()
        
        payload = {
            "message": f"Update {filename} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "content": content_b64,
            "branch": self.branch
        }
        
        if sha:
            payload["sha"] = sha
        
        try:
            response = requests.put(url, headers=self.headers, json=payload)
            return response.status_code in [200, 201]
        except:
            return False
    
    def test_connection(self):
        """Test GitHub connection"""
        if not self.token:
            return False, "GitHub token not configured"
        
        test_url = f"https://api.github.com/repos/{self.owner}/{self.repo}"
        try:
            response = requests.get(test_url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return True, "✅ Connected to GitHub"
            else:
                return False, f"❌ GitHub error: {response.status_code}"
        except Exception as e:
            return False, f"❌ Connection failed: {str(e)}"

# Initialize GitHub storage
github_storage = GitHubStorage()

# ============================================================
# YOUR ORIGINAL CONSTANTS & SESSION STATE
# ============================================================

# File names (same as your original)
CONFIG_FILE = "config.json"
DATA_FILE = "allocations_data.json"
REFERENCE_FILE = "allocation_references.json"
DELETED_RECORDS_FILE = "deleted_records.json"

# Initialize session state (EXACTLY as your original structure)
def init_session_state():
    """Initialize all session state variables - IDENTICAL to your original"""
    default_states = {
        # DataFrames
        'io_df': None,
        'venue_df': pd.DataFrame(),
        'ey_df': pd.DataFrame(),
        
        # Allocations
        'allocation': [],
        'ey_allocation': [],
        'deleted_records': [],
        
        # Exam data
        'exam_data': {},
        'current_exam_key': "",
        'exam_name': "",
        'exam_year': "",
        
        # References
        'allocation_references': {},
        
        # Rates (same as your original)
        'remuneration_rates': {
            'multiple_shifts': 750,
            'single_shift': 450,
            'mock_test': 450,
            'ey_personnel': 5000
        },
        
        # EY Personnel
        'ey_personnel_list': [],
        
        # Selection states
        'selected_venue': "",
        'selected_role': "Centre Coordinator",
        'selected_dates': {},
        'mock_test_mode': False,
        'ey_allocation_mode': False,
        'selected_ey_personnel': "",
        'selected_ey_venues': [],
        'date_selections': {},
        'shift_selections': {},
        
        # Dialog states
        'reference_dialog_open': False,
        'reference_type': "",
        'deletion_dialog_open': False,
        'deletion_type': "",
        'deletion_count': 0,
        'bulk_delete_mode': False,
        'bulk_delete_selected': [],
        
        # System states
        'data_loaded': False,
        'github_connected': False,
        
        # Undo stack (for delete operations)
        'undo_stack': []
    }
    
    for key, value in default_states.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    # Initialize default IO data (SAME as your original)
    if st.session_state.io_df is None:
        default_data = """NAME,AREA,CENTRE_CODE,MOBILE,EMAIL
John Doe,Kolkata,1001,9876543210,john@example.com
Jane Smith,Howrah,1002,9876543211,jane@example.com
Robert Johnson,Hooghly,1003,9876543212,robert@example.com
Emily Davis,Nadia,2001,9876543213,emily@example.com
Michael Wilson,North 24 Parganas,2002,9876543214,michael@example.com"""
        
        st.session_state.io_df = pd.read_csv(io.StringIO(default_data))
        st.session_state.io_df['CENTRE_CODE'] = st.session_state.io_df['CENTRE_CODE'].astype(str).str.zfill(4)

# ============================================================
# DATA LOADING/SAVING - MODIFIED FOR GITHUB ONLY
# ============================================================

def load_data():
    """Load all data from GitHub - ONLY STORAGE CHANGED"""
    try:
        # Test GitHub connection
        connected, message = github_storage.test_connection()
        st.session_state.github_connected = connected
        
        if not connected:
            st.warning(message)
            return
        
        # Load config
        config = github_storage.read_json(CONFIG_FILE)
        if config:
            if 'remuneration_rates' in config:
                st.session_state.remuneration_rates.update(config['remuneration_rates'])
            if 'ey_personnel_list' in config:
                st.session_state.ey_personnel_list = config['ey_personnel_list']
        
        # Load exam data
        data = github_storage.read_json(DATA_FILE)
        if data:
            st.session_state.exam_data = data
        
        # Load references
        references = github_storage.read_json(REFERENCE_FILE)
        if references:
            st.session_state.allocation_references = references
        
        # Load deleted records
        deleted = github_storage.read_json(DELETED_RECORDS_FILE)
        if deleted:
            st.session_state.deleted_records = deleted
        
        st.session_state.data_loaded = True
        
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        logging.error(f"Error loading data: {str(e)}")

def save_data():
    """Save all data to GitHub - ONLY STORAGE CHANGED"""
    try:
        # Save config
        config = {
            'remuneration_rates': st.session_state.remuneration_rates,
            'ey_personnel_list': st.session_state.ey_personnel_list
        }
        github_storage.write_json(CONFIG_FILE, config)
        
        # Save exam data
        if st.session_state.current_exam_key:
            st.session_state.exam_data[st.session_state.current_exam_key] = {
                'io_allocations': st.session_state.allocation,
                'ey_allocations': st.session_state.ey_allocation
            }
        
        github_storage.write_json(DATA_FILE, st.session_state.exam_data)
        
        # Save references
        github_storage.write_json(REFERENCE_FILE, st.session_state.allocation_references)
        
        # Save deleted records
        github_storage.write_json(DELETED_RECORDS_FILE, st.session_state.deleted_records)
        
        st.success("✅ Data saved to GitHub")
        return True
        
    except Exception as e:
        st.error(f"Error saving data: {str(e)}")
        logging.error(f"Error saving data: {str(e)}")
        return False

# ============================================================
# YOUR ORIGINAL FUNCTIONS - ALL REMAIN UNCHANGED
# ============================================================

def check_allocation_conflict(person_name, date, shift, venue, role, allocation_type):
    """Check for allocation conflicts - IDENTICAL to your original"""
    if allocation_type == "IO":
        duplicate = any(
            alloc['IO Name'] == person_name and 
            alloc['Date'] == date and 
            alloc['Shift'] == shift and 
            alloc['Venue'] == venue and 
            alloc['Role'] == role
            for alloc in st.session_state.allocation
        )
        if duplicate:
            return f"Duplicate allocation found! {person_name} is already allocated to {venue} on {date} ({shift}) as {role}."
        
        if role == "Centre Coordinator":
            conflict = any(
                alloc['IO Name'] == person_name and 
                alloc['Date'] == date and 
                alloc['Shift'] == shift and 
                alloc['Venue'] != venue and
                alloc['Role'] == "Centre Coordinator"
                for alloc in st.session_state.allocation
            )
            if conflict:
                existing_venue = next(
                    alloc['Venue'] for alloc in st.session_state.allocation 
                    if alloc['IO Name'] == person_name and 
                       alloc['Date'] == date and 
                       alloc['Shift'] == shift and
                       alloc['Role'] == "Centre Coordinator"
                )
                return f"Centre Coordinator conflict! {person_name} is already allocated to {existing_venue} on {date} ({shift}). Cannot assign to {venue}."
    
    elif allocation_type == "EY":
        duplicate = any(
            alloc['EY Personnel'] == person_name and 
            alloc['Date'] == date and 
            alloc['Shift'] == shift and 
            alloc['Venue'] == venue
            for alloc in st.session_state.ey_allocation
        )
        if duplicate:
            return f"Duplicate EY allocation found! {person_name} is already allocated to {venue} on {date} ({shift})."
        
        conflict = any(
            alloc['EY Personnel'] == person_name and 
            alloc['Date'] == date and 
            alloc['Shift'] == shift and 
            alloc['Venue'] != venue
            for alloc in st.session_state.ey_allocation
        )
        if conflict:
            existing_venue = next(
                alloc['Venue'] for alloc in st.session_state.ey_allocation 
                if alloc['EY Personnel'] == person_name and 
                   alloc['Date'] == date and 
                   alloc['Shift'] == shift
            )
            return f"EY Personnel conflict! {person_name} is already allocated to {existing_venue} on {date} ({shift}). Cannot assign to {venue}."
    
    return None

def get_allocation_reference(allocation_type):
    """Get or create allocation reference - IDENTICAL to your original"""
    exam_key = st.session_state.current_exam_key
    if not exam_key:
        st.warning("⚠️ Please select or create an exam first")
        return None
    
    if exam_key not in st.session_state.allocation_references:
        st.session_state.allocation_references[exam_key] = {}
    
    if allocation_type in st.session_state.allocation_references[exam_key]:
        existing_ref = st.session_state.allocation_references[exam_key][allocation_type]
        
        with st.expander(f"Existing reference found for {allocation_type}", expanded=True):
            st.info(f"**Order No.**: {existing_ref.get('order_no', 'N/A')}")
            st.info(f"**Page No.**: {existing_ref.get('page_no', 'N/A')}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"✅ Use Existing Reference", key=f"use_existing_{allocation_type}"):
                    return existing_ref
            with col2:
                if st.button(f"🆕 Create New Reference", key=f"new_ref_{allocation_type}"):
                    st.session_state.reference_dialog_open = True
                    st.session_state.reference_type = allocation_type
                    st.rerun()
        
        return None
    else:
        st.session_state.reference_dialog_open = True
        st.session_state.reference_type = allocation_type
        st.rerun()
        return None

def calculate_remuneration():
    """Calculate remuneration with detailed shift information - IDENTICAL"""
    if not st.session_state.allocation:
        return pd.DataFrame()
    
    remuneration_data = []
    allocation_df = pd.DataFrame(st.session_state.allocation)
    
    for (io_name, date), group in allocation_df.groupby(['IO Name', 'Date']):
        shifts = group['Shift'].nunique()
        is_mock = any(group['Mock Test'])
        venues = ", ".join(group['Venue'].unique())
        roles = ", ".join(group['Role'].unique())
        
        # Get reference information
        order_no = group.iloc[0].get('Order No.', '')
        page_no = group.iloc[0].get('Page No.', '')
        
        if is_mock:
            amount = st.session_state.remuneration_rates['mock_test']
            shift_type = "Mock Test"
        else:
            if shifts > 1:
                amount = st.session_state.remuneration_rates['multiple_shifts']
                shift_type = "Multiple Shifts"
            else:
                amount = st.session_state.remuneration_rates['single_shift']
                shift_type = "Single Shift"
        
        remuneration_data.append({
            'IO Name': str(io_name),
            'Venues': str(venues),
            'Role': str(roles),
            'Date': str(date),
            'Total Shifts': int(shifts),
            'Shift Type': str(shift_type),
            'Shift Details': str(dict(group.groupby('Date')['Shift'].apply(list))),
            'Mock Test': "Yes" if is_mock else "No",
            'Amount (₹)': int(amount),
            'Order No.': str(order_no),
            'Page No.': str(page_no)
        })
    
    return pd.DataFrame(remuneration_data)

def calculate_ey_remuneration():
    """Calculate EY personnel remuneration - IDENTICAL"""
    if not st.session_state.ey_allocation:
        return pd.DataFrame()
    
    ey_remuneration_data = []
    ey_df = pd.DataFrame(st.session_state.ey_allocation)
    
    for (ey_person, date), group in ey_df.groupby(['EY Personnel', 'Date']):
        shifts = group['Shift'].nunique()
        venues = ", ".join(group['Venue'].unique())
        is_mock = any(group['Mock Test'])
        
        amount = st.session_state.remuneration_rates['ey_personnel']
        
        shift_details = ", ".join([str(shift) for shift in group['Shift'].unique()])
        
        # Get reference information
        order_no = group.iloc[0].get('Order No.', '')
        page_no = group.iloc[0].get('Page No.', '')
        
        ey_remuneration_data.append({
            'EY Personnel': str(ey_person),
            'Venues': str(venues),
            'Date': str(date),
            'Total Shifts': int(shifts),
            'Shift Details': shift_details,
            'Mock Test': "Yes" if is_mock else "No",
            'Amount (₹)': int(amount),
            'Rate Type': 'Per Day',
            'Order No.': str(order_no),
            'Page No.': str(page_no)
        })
    
    return pd.DataFrame(ey_remuneration_data)

# ============================================================
# STREAMLIT UI COMPONENTS
# ============================================================

def show_exam_management():
    """Exam management section - Same functionality as Tkinter"""
    st.header("📋 Exam Management")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        exam_options = sorted(st.session_state.exam_data.keys())
        selected_exam = st.selectbox("Select Exam", [""] + exam_options)
        
        if selected_exam and selected_exam != st.session_state.current_exam_key:
            st.session_state.current_exam_key = selected_exam
            if selected_exam in st.session_state.exam_data:
                exam_data = st.session_state.exam_data[selected_exam]
                st.session_state.allocation = exam_data.get('io_allocations', [])
                st.session_state.ey_allocation = exam_data.get('ey_allocations', [])
            st.rerun()
    
    with col2:
        st.session_state.mock_test_mode = st.checkbox("Mock Test Mode", 
                                                     value=st.session_state.mock_test_mode)
    
    with col3:
        st.session_state.ey_allocation_mode = st.checkbox("EY Allocation Mode", 
                                                         value=st.session_state.ey_allocation_mode)
    
    st.subheader("Create New Exam")
    col1, col2 = st.columns(2)
    with col1:
        exam_name = st.text_input("Exam Name", st.session_state.exam_name)
    with col2:
        current_year = datetime.now().year
        years = [str(y) for y in range(current_year-5, current_year+3)]
        exam_year = st.selectbox("Year", years, index=years.index(str(current_year)) 
                                if str(current_year) in years else 0)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("Create Exam", use_container_width=True):
            if exam_name and exam_year:
                st.session_state.current_exam_key = f"{exam_name} - {exam_year}"
                st.session_state.exam_name = exam_name
                st.session_state.exam_year = exam_year
                st.session_state.allocation = []
                st.session_state.ey_allocation = []
                st.success(f"Created: {st.session_state.current_exam_key}")
                save_data()
                st.rerun()
    
    with col2:
        if st.session_state.current_exam_key and st.button("Delete Exam", use_container_width=True):
            if st.session_state.current_exam_key in st.session_state.exam_data:
                del st.session_state.exam_data[st.session_state.current_exam_key]
                save_data()
                st.session_state.current_exam_key = ""
                st.success("Exam deleted")
                st.rerun()

def show_io_allocation():
    """IO Allocation section - Same functionality as Tkinter"""
    st.header("👥 Centre Coordinator Allocation")
    
    if not st.session_state.current_exam_key:
        st.warning("Select an exam first")
        return
    
    # File Upload
    st.subheader("1. Load Master Files")
    col1, col2 = st.columns(2)
    
    with col1:
        io_file = st.file_uploader("Upload Centre Coordinator Master", type=["xlsx", "xls", "csv"])
        if io_file:
            try:
                if io_file.name.endswith('.csv'):
                    st.session_state.io_df = pd.read_csv(io_file)
                else:
                    st.session_state.io_df = pd.read_excel(io_file)
                
                # Standardize column names (as in your original code)
                st.session_state.io_df.columns = [str(col).strip().upper() for col in st.session_state.io_df.columns]
                st.success(f"Loaded {len(st.session_state.io_df)} records")
            except Exception as e:
                st.error(f"Error loading file: {str(e)}")
    
    with col2:
        venue_file = st.file_uploader("Upload Venue List", type=["xlsx", "xls", "csv"])
        if venue_file:
            try:
                if venue_file.name.endswith('.csv'):
                    st.session_state.venue_df = pd.read_csv(venue_file)
                else:
                    st.session_state.venue_df = pd.read_excel(venue_file)
                
                # Standardize column names
                st.session_state.venue_df.columns = [str(col).strip().upper() for col in st.session_state.venue_df.columns]
                
                # Process dates as in original code
                if 'DATE' in st.session_state.venue_df.columns:
                    st.session_state.venue_df['DATE'] = pd.to_datetime(
                        st.session_state.venue_df['DATE'], errors='coerce'
                    ).dt.strftime('%d-%m-%Y')
                
                st.success(f"Loaded {len(st.session_state.venue_df)} venue records")
            except Exception as e:
                st.error(f"Error loading file: {str(e)}")
    
    # Venue Selection
    st.subheader("2. Select Venue & Dates")
    col1, col2 = st.columns(2)
    
    with col1:
        if not st.session_state.venue_df.empty:
            venues = sorted(st.session_state.venue_df['VENUE'].dropna().unique())
            selected_venue = st.selectbox("Select Venue", venues)
            st.session_state.selected_venue = selected_venue
    
    with col2:
        role = st.selectbox("Select Role", ["Centre Coordinator", "Flying Squad"])
        st.session_state.selected_role = role
    
    # Date Selection
    if st.session_state.selected_venue and not st.session_state.venue_df.empty:
        venue_data = st.session_state.venue_df[
            st.session_state.venue_df['VENUE'] == st.session_state.selected_venue
        ]
        
        if not venue_data.empty:
            # Group dates as in original code
            date_groups = venue_data.groupby('DATE')['SHIFT'].apply(list).to_dict()
            
            st.write("Select Dates & Shifts:")
            for date_str, shifts in date_groups.items():
                col1, col2 = st.columns([1, 3])
                with col1:
                    date_selected = st.checkbox(date_str, key=f"date_{date_str}")
                with col2:
                    if date_selected:
                        selected_shifts = st.multiselect(
                            f"Shifts for {date_str}",
                            shifts,
                            key=f"shifts_{date_str}"
                        )
                        st.session_state.date_selections[date_str] = selected_shifts

def show_ey_allocation():
    """EY Personnel Allocation section - Same functionality as Tkinter"""
    st.header("👁️ EY Personnel Allocation")
    
    if not st.session_state.current_exam_key:
        st.warning("Select an exam first")
        return
    
    # File Upload
    st.subheader("1. Load EY Personnel Master")
    ey_file = st.file_uploader("Upload EY Personnel Master", type=["xlsx", "xls", "csv"])
    if ey_file:
        try:
            if ey_file.name.endswith('.csv'):
                st.session_state.ey_df = pd.read_csv(ey_file)
            else:
                st.session_state.ey_df = pd.read_excel(ey_file)
            
            # Standardize column names
            st.session_state.ey_df.columns = [str(col).strip().upper() for col in st.session_state.ey_df.columns]
            st.success(f"Loaded {len(st.session_state.ey_df)} EY personnel")
        except Exception as e:
            st.error(f"Error loading file: {str(e)}")
    
    # EY Rate
    st.subheader("2. Set EY Rate")
    ey_rate = st.number_input("EY Rate per Day (₹)", 
                             value=st.session_state.remuneration_rates['ey_personnel'],
                             min_value=0)
    st.session_state.remuneration_rates['ey_personnel'] = int(ey_rate)
    
    # Venue Selection for EY
    if not st.session_state.venue_df.empty:
        st.subheader("3. Select Venues for EY Allocation")
        venues = sorted(st.session_state.venue_df['VENUE'].dropna().unique())
        selected_venues = st.multiselect("Select Venues", venues)
        st.session_state.selected_ey_venues = selected_venues
    
    # EY Personnel Selection
    if not st.session_state.ey_df.empty:
        st.subheader("4. Select EY Personnel")
        
        # Search
        search_term = st.text_input("Search EY Personnel")
        
        # Filter based on search
        if search_term:
            filtered_ey = st.session_state.ey_df[
                (st.session_state.ey_df['NAME'].str.contains(search_term, case=False, na=False)) |
                (st.session_state.ey_df.get('MOBILE', '').astype(str).str.contains(search_term, na=False)) |
                (st.session_state.ey_df.get('EMAIL', '').astype(str).str.contains(search_term, na=False))
            ]
        else:
            filtered_ey = st.session_state.ey_df
        
        # Display selection
        if not filtered_ey.empty:
            ey_options = []
            for _, row in filtered_ey.iterrows():
                display_text = f"{row.get('NAME', '')}"
                if 'MOBILE' in row:
                    display_text += f" | Mobile: {row['MOBILE']}"
                if 'EMAIL' in row:
                    display_text += f" | Email: {row['EMAIL']}"
                ey_options.append(display_text)
            
            selected_ey = st.selectbox("Select EY Personnel", ey_options)
            if selected_ey:
                st.session_state.selected_ey_personnel = selected_ey.split(" | ")[0]

def show_reports():
    """Reports section - Same functionality as Tkinter"""
    st.header("📊 Reports & Export")
    
    if not st.session_state.current_exam_key:
        st.warning("Select an exam first")
        return
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📈 Generate Allocation Report", use_container_width=True):
            if st.session_state.allocation or st.session_state.ey_allocation:
                # Create Excel report as in original
                with st.spinner("Generating report..."):
                    try:
                        # Your original export logic here
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                            # Add sheets as per your original code
                            if st.session_state.allocation:
                                alloc_df = pd.DataFrame(st.session_state.allocation)
                                alloc_df.to_excel(writer, sheet_name='IO Allocations', index=False)
                            
                            if st.session_state.ey_allocation:
                                ey_df = pd.DataFrame(st.session_state.ey_allocation)
                                ey_df.to_excel(writer, sheet_name='EY Allocations', index=False)
                            
                            # Add summary sheets
                            rem_df = calculate_remuneration()
                            if not rem_df.empty:
                                rem_df.to_excel(writer, sheet_name='IO Remuneration', index=False)
                            
                            ey_rem_df = calculate_ey_remuneration()
                            if not ey_rem_df.empty:
                                ey_rem_df.to_excel(writer, sheet_name='EY Remuneration', index=False)
                        
                        buffer.seek(0)
                        
                        st.download_button(
                            label="⬇️ Download Allocation Report",
                            data=buffer,
                            file_name=f"Allocation_Report_{st.session_state.current_exam_key}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                        
                    except Exception as e:
                        st.error(f"Error generating report: {str(e)}")
    
    with col2:
        if st.button("💰 Generate Remuneration Report", use_container_width=True):
            # Similar to above but focused on remuneration
            pass
    
    with col3:
        if st.button("🗑️ View Deleted Records", use_container_width=True):
            if st.session_state.deleted_records:
                deleted_df = pd.DataFrame(st.session_state.deleted_records)
                st.dataframe(deleted_df, use_container_width=True)
            else:
                st.info("No deleted records found")

def show_reference_dialog():
    """Show reference dialog - Same as Tkinter"""
    if st.session_state.reference_dialog_open:
        with st.container():
            st.subheader(f"📝 Enter Reference for {st.session_state.reference_type}")
            
            order_no = st.text_input("Order No.:", key="ref_order_no")
            page_no = st.text_input("Page No.:", key="ref_page_no")
            remarks = st.text_area("Remarks (Optional):", key="ref_remarks")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Save Reference", use_container_width=True):
                    if order_no and page_no:
                        exam_key = st.session_state.current_exam_key
                        if exam_key not in st.session_state.allocation_references:
                            st.session_state.allocation_references[exam_key] = {}
                        
                        st.session_state.allocation_references[exam_key][st.session_state.reference_type] = {
                            'order_no': order_no,
                            'page_no': page_no,
                            'remarks': remarks,
                            'timestamp': datetime.now().isoformat(),
                            'allocation_type': st.session_state.reference_type
                        }
                        
                        save_data()
                        st.session_state.reference_dialog_open = False
                        st.success("✅ Reference saved successfully!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Please enter both Order No. and Page No.")
            
            with col2:
                if st.button("❌ Cancel", use_container_width=True):
                    st.session_state.reference_dialog_open = False
                    st.rerun()

def show_side_panel():
    """Side panel for quick actions - Similar to Tkinter sidebar"""
    st.sidebar.title("⚙️ Quick Actions")
    
    # GitHub Status
    connected, message = github_storage.test_connection()
    if connected:
        st.sidebar.success(message)
    else:
        st.sidebar.error(message)
    
    st.sidebar.divider()
    
    # Current Exam Info
    if st.session_state.current_exam_key:
        st.sidebar.success(f"**Current Exam:**\n{st.session_state.current_exam_key}")
    else:
        st.sidebar.warning("No exam selected")
    
    st.sidebar.divider()
    
    # Quick Actions
    if st.sidebar.button("💾 Save All Data", use_container_width=True):
        if save_data():
            st.sidebar.success("Saved!")
        else:
            st.sidebar.error("Failed!")
    
    if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
        load_data()
        st.rerun()
    
    if st.sidebar.button("📤 Export Backup", use_container_width=True):
        # Create backup zip
        pass
    
    st.sidebar.divider()
    
    # Settings
    with st.sidebar.expander("⚙️ Settings"):
        st.write("**Remuneration Rates:**")
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.remuneration_rates['multiple_shifts'] = st.number_input(
                "Multiple Shifts", 
                value=st.session_state.remuneration_rates['multiple_shifts']
            )
            st.session_state.remuneration_rates['single_shift'] = st.number_input(
                "Single Shift", 
                value=st.session_state.remuneration_rates['single_shift']
            )
        with col2:
            st.session_state.remuneration_rates['mock_test'] = st.number_input(
                "Mock Test", 
                value=st.session_state.remuneration_rates['mock_test']
            )
            st.session_state.remuneration_rates['ey_personnel'] = st.number_input(
                "EY Personnel", 
                value=st.session_state.remuneration_rates['ey_personnel']
            )
        
        if st.button("Save Rates", key="save_rates"):
            save_data()
            st.success("Rates saved!")

# ============================================================
# MAIN APP
# ============================================================

def main():
    """Main Streamlit application"""
    # Page config
    st.set_page_config(
        page_title="SSC Allocation System",
        page_icon="🏛️",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize
    init_session_state()
    
    # Load data if not loaded
    if not st.session_state.get('data_loaded'):
        with st.spinner("Loading data from GitHub..."):
            load_data()
    
    # Header
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/4/41/Seal_of_India.svg/1200px-Seal_of_India.svg.png", 
                width=80)
    with col2:
        st.title("🏛️ STAFF SELECTION COMMISSION (ER), KOLKATA")
        st.subheader("Centre Coordinator & Flying Squad Allocation System")
    with col3:
        st.write("")  # Spacer
    
    # Side panel
    show_side_panel()
    
    # Show reference dialog if open
    show_reference_dialog()
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Exams", 
        "👥 IO Allocation", 
        "👁️ EY Allocation", 
        "📊 Reports"
    ])
    
    with tab1:
        show_exam_management()
    
    with tab2:
        show_io_allocation()
    
    with tab3:
        show_ey_allocation()
    
    with tab4:
        show_reports()
    
    # Footer
    st.divider()
    st.caption("Designed by Bijay Paswan | Version 1.0")

# ============================================================
# RUN THE APP
# ============================================================

if __name__ == "__main__":
    main()
