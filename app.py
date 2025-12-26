# app.py
import streamlit as st
import pandas as pd
from datetime import datetime
import json
import logging
import io
import base64
import time
import requests
import hashlib

# ============================================================
# GITHUB REPOSITORY CONFIGURATION
# ============================================================
GITHUB_OWNER = st.secrets.get("GITHUB_OWNER", "your_github_username")
GITHUB_REPO = st.secrets.get("GITHUB_REPO", "cc_fso_allocation_data")
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
GITHUB_BRANCH = st.secrets.get("GITHUB_BRANCH", "main")

# GitHub URLs
GITHUB_API_BASE = "https://api.github.com"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com"

# File paths in GitHub
CONFIG_FILE_PATH = "config.json"
DATA_FILE_PATH = "allocations_data.json"
REFERENCE_FILE_PATH = "allocation_references.json"
DELETED_FILE_PATH = "deleted_records.json"

# Headers for GitHub API
API_HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ============================================================
# GITHUB DATA HANDLING FUNCTIONS
# ============================================================

def get_github_raw_url(file_path):
    """Get URL for raw GitHub content"""
    return f"{GITHUB_RAW_BASE}/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/{file_path}"

def get_github_api_url(file_path=None):
    """Get URL for GitHub API"""
    if file_path:
        return f"{GITHUB_API_BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{file_path}"
    return f"{GITHUB_API_BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}"

def load_from_github(file_path):
    """Load JSON data from GitHub"""
    url = get_github_raw_url(file_path)
    headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            logging.info(f"File {file_path} not found on GitHub, will be created")
            return None
        else:
            logging.error(f"Error loading {file_path}: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"Failed to load {file_path}: {str(e)}")
        return None

def save_to_github(file_path, data):
    """Save data to GitHub using API"""
    api_url = get_github_api_url(file_path)
    
    # Get existing file SHA if exists
    sha = None
    try:
        response = requests.get(api_url, headers=API_HEADERS)
        if response.status_code == 200:
            sha = response.json().get("sha")
    except:
        pass  # File doesn't exist yet
    
    # Prepare content
    content = json.dumps(data, indent=4, ensure_ascii=False)
    content_b64 = base64.b64encode(content.encode('utf-8')).decode()
    
    payload = {
        "message": f"Update {file_path} via Streamlit App - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "content": content_b64,
        "branch": GITHUB_BRANCH
    }
    
    if sha:
        payload["sha"] = sha
    
    try:
        response = requests.put(api_url, headers=API_HEADERS, json=payload)
        if response.status_code in [200, 201]:
            logging.info(f"Successfully saved {file_path} to GitHub")
            return True
        else:
            logging.error(f"Failed to save {file_path}: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logging.error(f"Exception saving to GitHub: {str(e)}")
        return False

def check_github_connection():
    """Check if GitHub connection works"""
    try:
        response = requests.get(
            get_github_api_url(),
            headers=API_HEADERS,
            timeout=10
        )
        return response.status_code == 200
    except:
        return False

# ============================================================
# INITIALIZE SESSION STATE
# ============================================================
def init_session_state():
    default_states = {
        'io_df': None,
        'venue_df': pd.DataFrame(),
        'ey_df': pd.DataFrame(),
        'allocation': [],
        'ey_allocation': [],
        'deleted_records': [],
        'exam_data': {},
        'current_exam_key': "",
        'exam_name': "",
        'exam_year': "",
        'allocation_references': {},
        'remuneration_rates': {
            'multiple_shifts': 1500,
            'single_shift': 900,
            'mock_test': 900,
            'ey_personnel': 6950
        },
        'ey_personnel_list': [],
        'selected_venue': "",
        'selected_role': "Centre Coordinator",
        'selected_dates': {},
        'mock_test_mode': False,
        'ey_allocation_mode': False,
        'selected_ey_personnel': "",
        'selected_ey_venues': [],
        'date_selections': {},
        'shift_selections': {},
        'reference_dialog_open': False,
        'reference_type': "",
        'deletion_dialog_open': False,
        'deletion_type': "",
        'deletion_count': 0,
        'bulk_delete_mode': False,
        'bulk_delete_selected': [],
        'github_connected': False,
        'last_sync': None,
        'data_loaded': False
    }
    
    for key, value in default_states.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    # Initialize default IO data
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
# LOAD AND SAVE DATA
# ============================================================
def load_data():
    """Load all data from GitHub with proper format handling"""
    try:
        # Check GitHub connection
        if not check_github_connection():
            st.error("❌ Cannot connect to GitHub. Check your token and repository settings.")
            st.session_state.github_connected = False
            return
        
        # Load config
        config = load_from_github(CONFIG_FILE_PATH)
        if config:
            if 'remuneration_rates' in config:
                st.session_state.remuneration_rates.update(config['remuneration_rates'])
            if 'ey_personnel_list' in config:
                st.session_state.ey_personnel_list = config.get('ey_personnel_list', [])
        
        # Load allocations data
        allocations_data = load_from_github(DATA_FILE_PATH)
        if allocations_data:
            st.session_state.exam_data = allocations_data
        
        # Load references
        references = load_from_github(REFERENCE_FILE_PATH)
        if references:
            st.session_state.allocation_references = references
        
        # Load deleted records
        deleted = load_from_github(DELETED_FILE_PATH)
        if deleted:
            st.session_state.deleted_records = deleted
        
        st.session_state.github_connected = True
        st.session_state.last_sync = datetime.now()
        st.session_state.data_loaded = True
        
        # Load current exam data if exists
        if st.session_state.current_exam_key and st.session_state.current_exam_key in st.session_state.exam_data:
            exam_data = st.session_state.exam_data[st.session_state.current_exam_key]
            if isinstance(exam_data, dict):
                st.session_state.allocation = exam_data.get('io_allocations', [])
                st.session_state.ey_allocation = exam_data.get('ey_allocations', [])
        
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        logging.error(f"Error loading data: {str(e)}")

def save_data():
    """Save all data to GitHub with proper format"""
    try:
        # Save config
        config = {
            'remuneration_rates': st.session_state.remuneration_rates,
            'ey_personnel_list': st.session_state.ey_personnel_list
        }
        
        # Save allocations data
        if st.session_state.current_exam_key:
            if st.session_state.current_exam_key not in st.session_state.exam_data:
                st.session_state.exam_data[st.session_state.current_exam_key] = {}
            
            st.session_state.exam_data[st.session_state.current_exam_key] = {
                'io_allocations': st.session_state.allocation,
                'ey_allocations': st.session_state.ey_allocation
            }
        
        # Save all data
        success = True
        success = success and save_to_github(CONFIG_FILE_PATH, config)
        success = success and save_to_github(DATA_FILE_PATH, st.session_state.exam_data)
        success = success and save_to_github(REFERENCE_FILE_PATH, st.session_state.allocation_references)
        success = success and save_to_github(DELETED_FILE_PATH, st.session_state.deleted_records)
        
        if success:
            st.session_state.last_sync = datetime.now()
            return True
        else:
            return False
            
    except Exception as e:
        st.error(f"Error saving data: {str(e)}")
        logging.error(f"Error saving data: {str(e)}")
        return False

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def check_allocation_conflict(person_name, date, shift, venue, role, allocation_type):
    """Check for allocation conflicts"""
    if allocation_type == "IO":
        # Check for duplicate allocation
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
        
        # For Centre Coordinator: Cannot be assigned to multiple venues on same date and shift
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
        # Check for duplicate allocation
        duplicate = any(
            alloc['EY Personnel'] == person_name and 
            alloc['Date'] == date and 
            alloc['Shift'] == shift and 
            alloc['Venue'] == venue
            for alloc in st.session_state.ey_allocation
        )
        if duplicate:
            return f"Duplicate EY allocation found! {person_name} is already allocated to {venue} on {date} ({shift})."
        
        # EY Personnel: Cannot be assigned to multiple venues on same date and shift
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
    """Get or create allocation reference"""
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
            if existing_ref.get('remarks'):
                st.info(f"**Remarks**: {existing_ref.get('remarks')}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"✅ Use Existing Reference", key=f"use_existing_{allocation_type}"):
                    st.session_state.reference_dialog_open = False
                    return existing_ref
            with col2:
                if st.button(f"🆕 Create New Reference", key=f"new_ref_{allocation_type}"):
                    st.session_state.reference_dialog_open = True
                    st.session_state.reference_type = allocation_type
                    st.rerun()
        
        st.stop()
    else:
        st.session_state.reference_dialog_open = True
        st.session_state.reference_type = allocation_type
        st.rerun()
    
    return None

def show_reference_dialog():
    """Show dialog for entering reference details"""
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
            
            st.markdown("---")

def show_deletion_dialog():
    """Show dialog for entering deletion details"""
    if st.session_state.deletion_dialog_open:
        with st.container():
            st.subheader(f"🗑️ Deletion Reference for {st.session_state.deletion_type}")
            
            order_no = st.text_input("Deletion Order No.:", key="del_order_no")
            reason = st.text_area("Deletion Reason:", key="del_reason", height=100)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Confirm Deletion", use_container_width=True):
                    if order_no and reason:
                        st.session_state.deletion_result = {
                            'order_no': order_no,
                            'reason': reason,
                            'confirmed': True
                        }
                        st.session_state.deletion_dialog_open = False
                        st.rerun()
                    else:
                        st.error("❌ Please enter both Order No. and Deletion Reason")
            
            with col2:
                if st.button("❌ Cancel", use_container_width=True):
                    st.session_state.deletion_dialog_open = False
                    st.session_state.deletion_result = None
                    st.rerun()
            
            st.markdown("---")

def ask_for_deletion_reference(allocation_type, entries_count):
    """Ask for deletion reference"""
    st.session_state.deletion_dialog_open = True
    st.session_state.deletion_type = allocation_type
    st.session_state.deletion_count = entries_count
    
    show_deletion_dialog()
    
    if 'deletion_result' in st.session_state and st.session_state.deletion_result:
        result = st.session_state.deletion_result
        del st.session_state.deletion_result
        return result
    
    return None

def view_allocation_references():
    """View all allocation references"""
    if not st.session_state.allocation_references:
        st.info("ℹ️ No allocation references found.")
        return
    
    st.subheader("📋 All Allocation References")
    
    all_refs = []
    for exam_key, roles in st.session_state.allocation_references.items():
        for role, ref in roles.items():
            timestamp = ref.get('timestamp', '')
            if timestamp:
                try:
                    timestamp = datetime.fromisoformat(timestamp).strftime('%d-%m-%Y %H:%M')
                except:
                    pass
            
            all_refs.append({
                "Exam": exam_key,
                "Role": role,
                "Order No.": ref.get('order_no', 'N/A'),
                "Page No.": ref.get('page_no', 'N/A'),
                "Timestamp": timestamp,
                "Remarks": ref.get('remarks', 'N/A')[:50] + "..." if len(ref.get('remarks', 'N/A')) > 50 else ref.get('remarks', 'N/A')
            })
    
    if all_refs:
        refs_df = pd.DataFrame(all_refs)
        st.dataframe(refs_df, use_container_width=True, hide_index=True)
        
        st.subheader("🗑️ Delete References")
        
        col_del1, col_del2, col_del3 = st.columns(3)
        
        with col_del1:
            if st.button("Delete Selected", use_container_width=True, disabled=True):
                st.info("Feature coming soon")
        
        with col_del2:
            exams = list(st.session_state.allocation_references.keys())
            if exams:
                selected_exam = st.selectbox("Select Exam:", exams, key="del_exam_select")
                if st.button("Delete Exam References", use_container_width=True):
                    if selected_exam in st.session_state.allocation_references:
                        del st.session_state.allocation_references[selected_exam]
                        save_data()
                        st.success(f"✅ Deleted all references for {selected_exam}")
                        time.sleep(1)
                        st.rerun()
        
        with col_del3:
            if st.button("Delete All References", use_container_width=True, type="secondary"):
                st.warning("⚠️ This will delete ALL allocation references!")
                confirm = st.checkbox("I confirm I want to delete ALL references")
                if confirm:
                    st.session_state.allocation_references = {}
                    save_data()
                    st.success("✅ All references deleted!")
                    time.sleep(1)
                    st.rerun()

def view_deleted_records():
    """View deleted records"""
    if not st.session_state.deleted_records:
        st.info("ℹ️ No deleted records found.")
        return
    
    st.subheader("🗑️ Deleted Records")
    
    deleted_list = []
    for record in st.session_state.deleted_records:
        if 'IO Name' in record:
            deleted_list.append({
                "Type": "Centre Coordinator",
                "Name": record['IO Name'],
                "Venue": record['Venue'],
                "Date": record['Date'],
                "Shift": record['Shift'],
                "Role": record.get('Role', 'N/A'),
                "Deletion Order No.": record.get('Deletion Order No.', 'N/A'),
                "Deletion Reason": record.get('Deletion Reason', 'N/A')[:50] + "..." if len(record.get('Deletion Reason', 'N/A')) > 50 else record.get('Deletion Reason', 'N/A'),
                "Timestamp": record.get('Deletion Timestamp', 'N/A')
            })
        else:
            deleted_list.append({
                "Type": "EY Personnel",
                "Name": record['EY Personnel'],
                "Venue": record['Venue'],
                "Date": record['Date'],
                "Shift": record['Shift'],
                "Role": "EY Personnel",
                "Deletion Order No.": record.get('Deletion Order No.', 'N/A'),
                "Deletion Reason": record.get('Deletion Reason', 'N/A')[:50] + "..." if len(record.get('Deletion Reason', 'N/A')) > 50 else record.get('Deletion Reason', 'N/A'),
                "Timestamp": record.get('Deletion Timestamp', 'N/A')
            })
    
    if deleted_list:
        deleted_df = pd.DataFrame(deleted_list)
        st.dataframe(deleted_df, use_container_width=True, hide_index=True)
        
        st.subheader("🗑️ Delete Records Permanently")
        
        col_del1, col_del2 = st.columns(2)
        
        with col_del1:
            if st.button("Delete Selected", use_container_width=True, disabled=True):
                st.info("Feature coming soon")
        
        with col_del2:
            if st.button("Delete All", use_container_width=True, type="secondary"):
                st.warning("⚠️ This will permanently delete ALL deleted records!")
                confirm = st.checkbox("I confirm I want to permanently delete ALL deleted records")
                if confirm:
                    st.session_state.deleted_records = []
                    save_data()
                    st.success("✅ All deleted records permanently deleted!")
                    time.sleep(1)
                    st.rerun()

def export_allocations_report():
    """Export allocations report"""
    if not st.session_state.allocation and not st.session_state.ey_allocation:
        st.warning("⚠️ No data to export.")
        return
    
    try:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # IO Allocations
            if st.session_state.allocation:
                alloc_df = pd.DataFrame(st.session_state.allocation)
                alloc_df.to_excel(writer, index=False, sheet_name='IO Allocations')
            
            # EY Allocations
            if st.session_state.ey_allocation:
                ey_alloc_df = pd.DataFrame(st.session_state.ey_allocation)
                ey_alloc_df.to_excel(writer, index=False, sheet_name='EY Allocations')
            
            # Deleted Records
            if st.session_state.deleted_records:
                deleted_df = pd.DataFrame(st.session_state.deleted_records)
                deleted_df.to_excel(writer, index=False, sheet_name='Deleted Records')
            
            writer.save()
        
        # Offer download
        filename = f"Allocation_Report_{st.session_state.current_exam_key.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        
        st.download_button(
            label="📥 Download Allocation Report",
            data=output.getvalue(),
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    except Exception as e:
        st.error(f"❌ Export failed: {str(e)}")

def export_remuneration_report():
    """Export remuneration report"""
    if not st.session_state.allocation and not st.session_state.ey_allocation:
        st.warning("⚠️ No data to export.")
        return
    
    try:
        # Calculate IO remuneration
        io_remuneration = []
        if st.session_state.allocation:
            alloc_df = pd.DataFrame(st.session_state.allocation)
            for (io_name, date), group in alloc_df.groupby(['IO Name', 'Date']):
                shifts = group['Shift'].nunique()
                is_mock = any(group['Mock Test'])
                
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
                
                io_remuneration.append({
                    'IO Name': io_name,
                    'Date': date,
                    'Total Shifts': shifts,
                    'Shift Type': shift_type,
                    'Amount (₹)': amount
                })
        
        # Calculate EY remuneration
        ey_remuneration = []
        if st.session_state.ey_allocation:
            ey_df = pd.DataFrame(st.session_state.ey_allocation)
            for (ey_person, date), group in ey_df.groupby(['EY Personnel', 'Date']):
                amount = st.session_state.remuneration_rates['ey_personnel']
                ey_remuneration.append({
                    'EY Personnel': ey_person,
                    'Date': date,
                    'Rate Type': 'Per Day',
                    'Amount (₹)': amount
                })
        
        # Create Excel writer
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # IO Remuneration
            if io_remuneration:
                io_rem_df = pd.DataFrame(io_remuneration)
                io_rem_df.to_excel(writer, index=False, sheet_name='IO Remuneration')
                
                # IO Summary
                io_summary = []
                for io_name in set(item['IO Name'] for item in io_remuneration):
                    io_data = [item for item in io_remuneration if item['IO Name'] == io_name]
                    total_amount = sum(item['Amount (₹)'] for item in io_data)
                    total_days = len(io_data)
                    
                    io_summary.append({
                        'IO Name': io_name,
                        'Total Days': total_days,
                        'Total Amount (₹)': total_amount
                    })
                
                if io_summary:
                    io_summary_df = pd.DataFrame(io_summary)
                    io_summary_df.to_excel(writer, index=False, sheet_name='IO Summary')
            
            # EY Remuneration
            if ey_remuneration:
                ey_rem_df = pd.DataFrame(ey_remuneration)
                ey_rem_df.to_excel(writer, index=False, sheet_name='EY Remuneration')
                
                # EY Summary
                ey_summary = []
                for ey_person in set(item['EY Personnel'] for item in ey_remuneration):
                    ey_data = [item for item in ey_remuneration if item['EY Personnel'] == ey_person]
                    total_amount = sum(item['Amount (₹)'] for item in ey_data)
                    total_days = len(ey_data)
                    
                    ey_summary.append({
                        'EY Personnel': ey_person,
                        'Total Days': total_days,
                        'Total Amount (₹)': total_amount
                    })
                
                if ey_summary:
                    ey_summary_df = pd.DataFrame(ey_summary)
                    ey_summary_df.to_excel(writer, index=False, sheet_name='EY Summary')
            
            # Rates
            rates_data = [
                {'Category': 'Multiple Shifts', 'Amount (₹)': st.session_state.remuneration_rates['multiple_shifts'], 'Reference': 'Per allocation'},
                {'Category': 'Single Shift', 'Amount (₹)': st.session_state.remuneration_rates['single_shift'], 'Reference': 'Per allocation'},
                {'Category': 'Mock Test', 'Amount (₹)': st.session_state.remuneration_rates['mock_test'], 'Reference': 'Per allocation'},
                {'Category': 'EY Personnel', 'Amount (₹)': st.session_state.remuneration_rates['ey_personnel'], 'Reference': 'Per day'}
            ]
            rates_df = pd.DataFrame(rates_data)
            rates_df.to_excel(writer, index=False, sheet_name='Rates')
            
            writer.save()
        
        # Offer download
        filename = f"Remuneration_Report_{st.session_state.current_exam_key.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        
        st.download_button(
            label="📥 Download Remuneration Report",
            data=output.getvalue(),
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    except Exception as e:
        st.error(f"❌ Export failed: {str(e)}")

def show_io_summary():
    """Show IO summary"""
    if not st.session_state.allocation:
        st.info("ℹ️ No Centre Coordinator allocations yet.")
        return
    
    alloc_df = pd.DataFrame(st.session_state.allocation)
    
    # Group by IO Name
    io_summary = alloc_df.groupby('IO Name').agg({
        'Venue': lambda x: ', '.join(sorted(set(x))),
        'Date': lambda x: ', '.join(sorted(set(x))),
        'Shift': 'count',
        'Role': lambda x: ', '.join(sorted(set(x)))
    }).reset_index()
    
    io_summary.columns = ['IO Name', 'Venues', 'Dates', 'Total Shifts', 'Roles']
    
    st.dataframe(io_summary, use_container_width=True, hide_index=True)
    
    # Statistics
    col_stat1, col_stat2, col_stat3 = st.columns(3)
    with col_stat1:
        st.metric("Total IOs", len(io_summary))
    with col_stat2:
        st.metric("Total Shifts", io_summary['Total Shifts'].sum())
    with col_stat3:
        unique_dates = set()
        for dates in io_summary['Dates']:
            unique_dates.update(dates.split(', '))
        st.metric("Unique Dates", len(unique_dates))

def show_ey_summary():
    """Show EY summary"""
    if not st.session_state.ey_allocation:
        st.info("ℹ️ No EY Personnel allocations yet.")
        return
    
    ey_df = pd.DataFrame(st.session_state.ey_allocation)
    
    # Group by EY Personnel
    ey_summary = ey_df.groupby('EY Personnel').agg({
        'Venue': lambda x: ', '.join(sorted(set(x))),
        'Date': lambda x: ', '.join(sorted(set(x))),
        'Shift': 'count'
    }).reset_index()
    
    ey_summary.columns = ['EY Personnel', 'Venues', 'Dates', 'Total Shifts']
    
    st.dataframe(ey_summary, use_container_width=True, hide_index=True)
    
    # Statistics
    col_stat1, col_stat2, col_stat3 = st.columns(3)
    with col_stat1:
        st.metric("Total EY Personnel", len(ey_summary))
    with col_stat2:
        st.metric("Total Shifts", ey_summary['Total Shifts'].sum())
    with col_stat3:
        unique_dates = set()
        for dates in ey_summary['Dates']:
            unique_dates.update(dates.split(', '))
        st.metric("Unique Dates", len(unique_dates))

def show_date_summary():
    """Show date summary"""
    if not st.session_state.allocation:
        st.info("ℹ️ No allocations yet.")
        return
    
    alloc_df = pd.DataFrame(st.session_state.allocation)
    
    # Group by Date
    date_summary = alloc_df.groupby('Date').agg({
        'Venue': 'nunique',
        'IO Name': 'nunique',
        'Shift': 'count'
    }).reset_index()
    
    date_summary.columns = ['Date', 'Unique Venues', 'Unique IOs', 'Total Shifts']
    date_summary = date_summary.sort_values('Date')
    
    st.dataframe(date_summary, use_container_width=True, hide_index=True)

# ============================================================
# MAIN APPLICATION
# ============================================================
def main():
    st.set_page_config(
        page_title="SSC (ER) Kolkata - Allocation System (GitHub)",
        page_icon="🏛️",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    init_session_state()
    
    # Load data on startup
    if not st.session_state.data_loaded:
        load_data()
    
    # Show reference dialog if open
    if st.session_state.reference_dialog_open:
        show_reference_dialog()
        return
    
    # Show deletion dialog if open
    if st.session_state.deletion_dialog_open:
        show_deletion_dialog()
        return
    
    # Header
    st.title("🏛️ STAFF SELECTION COMMISSION (ER), KOLKATA")
    st.subheader("Centre Coordinator & Flying Squad Allocation System")
    
    # Sidebar
    with st.sidebar:
        st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/4/41/Seal_of_India.svg/1200px-Seal_of_India.svg.png", 
                 width=100)
        
        st.markdown("---")
        
        # Current exam info
        if st.session_state.current_exam_key:
            st.success(f"**Current Exam:**\n{st.session_state.current_exam_key}")
            
            # Quick stats
            col1, col2 = st.columns(2)
            with col1:
                st.metric("👥 IO", len(st.session_state.allocation))
            with col2:
                st.metric("👁️ EY", len(st.session_state.ey_allocation))
        else:
            st.warning("No exam selected")
        
        # GitHub status
        st.markdown("---")
        st.markdown("**🌐 GitHub Status**")
        
        if st.session_state.github_connected:
            st.success("✅ Connected to GitHub")
            if st.session_state.last_sync:
                st.caption(f"Last sync: {st.session_state.last_sync.strftime('%H:%M:%S')}")
        else:
            st.error("❌ Not connected")
        
        if GITHUB_TOKEN:
            st.caption(f"Repo: {GITHUB_OWNER}/{GITHUB_REPO}")
        
        st.markdown("---")
        
        # Quick actions
        st.subheader("Quick Actions")
        
        if st.button("📁 New Exam", use_container_width=True):
            st.session_state.exam_name = ""
            st.session_state.exam_year = ""
            st.rerun()
        
        if st.button("💾 Save All Data", use_container_width=True):
            if save_data():
                st.success("✅ Data saved to GitHub!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Failed to save data")
        
        if st.button("🔄 Load from GitHub", use_container_width=True):
            load_data()
            st.success("✅ Data loaded from GitHub!")
            time.sleep(1)
            st.rerun()
        
        if st.button("🔄 Refresh App", use_container_width=True):
            st.rerun()
        
        st.markdown("---")
        
        # System info
        st.caption(f"**Version:** 2.0 (GitHub)")
        st.caption(f"**Last Updated:** {datetime.now().strftime('%d-%m-%Y %H:%M')}")
        st.caption("**Designed by Bijay Paswan**")
    
    # Main tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Exam Management", 
        "👥 Centre Coordinator", 
        "👁️ EY Personnel",
        "📊 Reports & Export",
        "⚙️ Settings"
    ])
    
    # Tab 1: Exam Management
    with tab1:
        st.header("📋 Exam Information Management")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Existing exams
            exam_options = sorted(st.session_state.exam_data.keys())
            selected_exam = st.selectbox(
                "Select Existing Exam",
                options=[""] + exam_options,
                key="exam_selector"
            )
            
            if selected_exam and selected_exam != st.session_state.current_exam_key:
                st.session_state.current_exam_key = selected_exam
                if selected_exam in st.session_state.exam_data:
                    exam_data = st.session_state.exam_data[selected_exam]
                    if isinstance(exam_data, dict):
                        st.session_state.allocation = exam_data.get('io_allocations', [])
                        st.session_state.ey_allocation = exam_data.get('ey_allocations', [])
                    else:
                        st.session_state.allocation = exam_data
                        st.session_state.ey_allocation = []
                    
                    if " - " in selected_exam:
                        try:
                            name, year = selected_exam.rsplit(" - ", 1)
                            st.session_state.exam_name = name.strip()
                            st.session_state.exam_year = year.strip()
                        except:
                            st.session_state.exam_name = selected_exam
                            st.session_state.exam_year = ""
                
                st.success(f"✅ Loaded exam: {selected_exam}")
                st.rerun()
            
            # New exam form
            st.subheader("Create/Update Exam")
            col_name, col_year = st.columns(2)
            with col_name:
                st.session_state.exam_name = st.text_input(
                    "Exam Name",
                    value=st.session_state.exam_name,
                    key="new_exam_name"
                )
            
            with col_year:
                current_year = datetime.now().year
                year_options = [str(y) for y in range(current_year-5, current_year+3)]
                st.session_state.exam_year = st.selectbox(
                    "Exam Year",
                    options=[""] + year_options,
                    index=0 if not st.session_state.exam_year else (year_options.index(st.session_state.exam_year) if st.session_state.exam_year in year_options else 0),
                    key="new_exam_year"
                )
        
        with col2:
            st.subheader("Actions")
            
            # Create/Update button
            if st.button("🚀 Create/Update Exam", use_container_width=True, type="primary"):
                if not st.session_state.exam_name or not st.session_state.exam_year:
                    st.error("❌ Please enter both Exam Name and Year")
                else:
                    exam_key = f"{st.session_state.exam_name} - {st.session_state.exam_year}"
                    st.session_state.current_exam_key = exam_key
                    
                    if exam_key not in st.session_state.exam_data:
                        st.session_state.exam_data[exam_key] = {
                            'io_allocations': [],
                            'ey_allocations': []
                        }
                        st.session_state.allocation = []
                        st.session_state.ey_allocation = []
                    
                    if save_data():
                        st.success(f"✅ Exam set: {exam_key}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Failed to save exam data")
            
            # Delete button
            if st.session_state.current_exam_key:
                if st.button("🗑️ Delete Exam", use_container_width=True, type="secondary"):
                    st.warning(f"⚠️ This will delete '{st.session_state.current_exam_key}' and all its allocations!")
                    confirm = st.checkbox("I confirm I want to delete this exam")
                    if confirm:
                        # Remove from exam data
                        if st.session_state.current_exam_key in st.session_state.exam_data:
                            del st.session_state.exam_data[st.session_state.current_exam_key]
                        
                        # Remove references
                        if st.session_state.current_exam_key in st.session_state.allocation_references:
                            del st.session_state.allocation_references[st.session_state.current_exam_key]
                        
                        # Clear current allocations
                        st.session_state.allocation = []
                        st.session_state.ey_allocation = []
                        st.session_state.current_exam_key = ""
                        st.session_state.exam_name = ""
                        st.session_state.exam_year = ""
                        
                        if save_data():
                            st.success("✅ Exam deleted successfully!")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Failed to delete exam")
        
        # Allocation References Section
        if st.session_state.current_exam_key:
            st.divider()
            st.subheader("📋 Allocation References")
            
            exam_key = st.session_state.current_exam_key
            
            if exam_key not in st.session_state.allocation_references:
                st.session_state.allocation_references[exam_key] = {}
            
            col_ref1, col_ref2, col_ref3 = st.columns(3)
            
            with col_ref1:
                st.markdown("**Centre Coordinator**")
                if 'Centre Coordinator' in st.session_state.allocation_references[exam_key]:
                    ref = st.session_state.allocation_references[exam_key]['Centre Coordinator']
                    st.info(f"**Order No.**: {ref.get('order_no', 'N/A')}")
                    st.info(f"**Page No.**: {ref.get('page_no', 'N/A')}")
                    if ref.get('remarks'):
                        st.info(f"**Remarks**: {ref.get('remarks')}")
                else:
                    st.warning("No reference set")
                
                if st.button("✏️ Edit Reference", key="edit_cc_ref", use_container_width=True):
                    st.session_state.reference_dialog_open = True
                    st.session_state.reference_type = "Centre Coordinator"
                    if 'Centre Coordinator' in st.session_state.allocation_references[exam_key]:
                        existing_ref = st.session_state.allocation_references[exam_key]['Centre Coordinator']
                        st.session_state['ref_order_no'] = existing_ref.get('order_no', '')
                        st.session_state['ref_page_no'] = existing_ref.get('page_no', '')
                        st.session_state['ref_remarks'] = existing_ref.get('remarks', '')
                    st.rerun()
            
            with col_ref2:
                st.markdown("**Flying Squad**")
                if 'Flying Squad' in st.session_state.allocation_references[exam_key]:
                    ref = st.session_state.allocation_references[exam_key]['Flying Squad']
                    st.info(f"**Order No.**: {ref.get('order_no', 'N/A')}")
                    st.info(f"**Page No.**: {ref.get('page_no', 'N/A')}")
                    if ref.get('remarks'):
                        st.info(f"**Remarks**: {ref.get('remarks')}")
                else:
                    st.warning("No reference set")
                
                if st.button("✏️ Edit Reference", key="edit_fs_ref", use_container_width=True):
                    st.session_state.reference_dialog_open = True
                    st.session_state.reference_type = "Flying Squad"
                    if 'Flying Squad' in st.session_state.allocation_references[exam_key]:
                        existing_ref = st.session_state.allocation_references[exam_key]['Flying Squad']
                        st.session_state['ref_order_no'] = existing_ref.get('order_no', '')
                        st.session_state['ref_page_no'] = existing_ref.get('page_no', '')
                        st.session_state['ref_remarks'] = existing_ref.get('remarks', '')
                    st.rerun()
            
            with col_ref3:
                st.markdown("**EY Personnel**")
                if 'EY Personnel' in st.session_state.allocation_references[exam_key]:
                    ref = st.session_state.allocation_references[exam_key]['EY Personnel']
                    st.info(f"**Order No.**: {ref.get('order_no', 'N/A')}")
                    st.info(f"**Page No.**: {ref.get('page_no', 'N/A')}")
                    if ref.get('remarks'):
                        st.info(f"**Remarks**: {ref.get('remarks')}")
                else:
                    st.warning("No reference set")
                
                if st.button("✏️ Edit Reference", key="edit_ey_ref", use_container_width=True):
                    st.session_state.reference_dialog_open = True
                    st.session_state.reference_type = "EY Personnel"
                    if 'EY Personnel' in st.session_state.allocation_references[exam_key]:
                        existing_ref = st.session_state.allocation_references[exam_key]['EY Personnel']
                        st.session_state['ref_order_no'] = existing_ref.get('order_no', '')
                        st.session_state['ref_page_no'] = existing_ref.get('page_no', '')
                        st.session_state['ref_remarks'] = existing_ref.get('remarks', '')
                    st.rerun()
        
        # View All References
        st.divider()
        col_view1, col_view2 = st.columns(2)
        
        with col_view1:
            if st.button("👁️ View All References", use_container_width=True):
                view_allocation_references()
        
        with col_view2:
            if st.button("🗑️ View Deleted Records", use_container_width=True):
                view_deleted_records()
    
    # Tab 2: Centre Coordinator Allocation
    with tab2:
        st.header("👥 Centre Coordinator Allocation")
        
        if not st.session_state.current_exam_key:
            st.warning("⚠️ Please select or create an exam first from the Exam Management tab")
        else:
            # Configuration section
            col_config1, col_config2 = st.columns([2, 1])
            
            with col_config1:
                st.subheader("Step 1: Load Master Data")
                
                # File uploaders
                col_upload1, col_upload2 = st.columns(2)
                with col_upload1:
                    io_file = st.file_uploader(
                        "Upload Centre Coordinator Master (Excel)",
                        type=["xlsx", "xls"],
                        key="io_master_upload",
                        help="Excel file with NAME, AREA, CENTRE_CODE columns"
                    )
                    if io_file is not None:
                        try:
                            st.session_state.io_df = pd.read_excel(io_file)
                            st.session_state.io_df.columns = [str(col).strip().upper() for col in st.session_state.io_df.columns]
                            
                            required_cols = ["NAME", "AREA", "CENTRE_CODE"]
                            missing_cols = [col for col in required_cols if col not in st.session_state.io_df.columns]
                            
                            if missing_cols:
                                st.error(f"❌ Missing required columns: {', '.join(missing_cols)}")
                            else:
                                if 'CENTRE_CODE' in st.session_state.io_df.columns:
                                    st.session_state.io_df['CENTRE_CODE'] = st.session_state.io_df['CENTRE_CODE'].astype(str).str.zfill(4)
                                st.success(f"✅ Loaded {len(st.session_state.io_df)} Centre Coordinator records")
                        except Exception as e:
                            st.error(f"❌ Error loading file: {str(e)}")
                
                with col_upload2:
                    venue_file = st.file_uploader(
                        "Upload Venue List (Excel)",
                        type=["xlsx", "xls"],
                        key="venue_upload",
                        help="Excel file with VENUE, DATE, SHIFT, CENTRE_CODE, ADDRESS columns"
                    )
                    if venue_file is not None:
                        try:
                            st.session_state.venue_df = pd.read_excel(venue_file)
                            st.session_state.venue_df.columns = [str(col).strip().upper() for col in st.session_state.venue_df.columns]
                            
                            required_cols = ["VENUE", "DATE", "SHIFT", "CENTRE_CODE", "ADDRESS"]
                            missing_cols = [col for col in required_cols if col not in st.session_state.venue_df.columns]
                            
                            if missing_cols:
                                st.error(f"❌ Missing required columns: {', '.join(missing_cols)}")
                            else:
                                st.session_state.venue_df['VENUE'] = st.session_state.venue_df['VENUE'].astype(str).str.strip()
                                if 'CENTRE_CODE' in st.session_state.venue_df.columns:
                                    st.session_state.venue_df['CENTRE_CODE'] = st.session_state.venue_df['CENTRE_CODE'].astype(str).str.zfill(4)
                                st.session_state.venue_df['DATE'] = pd.to_datetime(st.session_state.venue_df['DATE'], errors='coerce').dt.strftime('%d-%m-%Y')
                                st.success(f"✅ Loaded {len(st.session_state.venue_df)} venue records")
                        except Exception as e:
                            st.error(f"❌ Error loading file: {str(e)}")
            
            with col_config2:
                st.subheader("Step 2: Configuration")
                
                # Mode and role selection
                st.session_state.mock_test_mode = st.checkbox(
                    "Mock Test Mode",
                    value=st.session_state.mock_test_mode,
                    key="mock_test_checkbox"
                )
                
                st.session_state.selected_role = st.selectbox(
                    "Select Role",
                    options=["Centre Coordinator", "Flying Squad"],
                    index=0,
                    key="role_selector"
                )
                
                # Remuneration Rates
                st.subheader("💰 Remuneration Rates")
                st.session_state.remuneration_rates['multiple_shifts'] = st.number_input(
                    "Multiple Shifts (₹)",
                    min_value=0,
                    value=st.session_state.remuneration_rates['multiple_shifts'],
                    key="multi_shift_rate"
                )
                st.session_state.remuneration_rates['single_shift'] = st.number_input(
                    "Single Shift (₹)",
                    min_value=0,
                    value=st.session_state.remuneration_rates['single_shift'],
                    key="single_shift_rate"
                )
                st.session_state.remuneration_rates['mock_test'] = st.number_input(
                    "Mock Test (₹)",
                    min_value=0,
                    value=st.session_state.remuneration_rates['mock_test'],
                    key="mock_test_rate"
                )
                
                if st.button("💾 Save Rates", use_container_width=True):
                    if save_data():
                        st.success("✅ Rates saved successfully!")
                    else:
                        st.error("❌ Failed to save rates")
            
            st.divider()
            
            # Step 3: Venue and Date Selection
            st.subheader("Step 3: Select Venue & Dates")
            
            if not st.session_state.venue_df.empty:
                venues = sorted(st.session_state.venue_df['VENUE'].dropna().unique())
                if venues:
                    st.session_state.selected_venue = st.selectbox(
                        "Select Venue",
                        options=venues,
                        index=0 if not st.session_state.selected_venue else (venues.index(st.session_state.selected_venue) if st.session_state.selected_venue in venues else 0),
                        key="venue_selector"
                    )
                    
                    if st.session_state.selected_venue:
                        # Get available dates for selected venue
                        venue_dates_df = st.session_state.venue_df[
                            st.session_state.venue_df['VENUE'] == st.session_state.selected_venue
                        ].copy()
                        
                        if not venue_dates_df.empty:
                            # Group by date and get shifts
                            date_shifts = {}
                            for date in venue_dates_df['DATE'].unique():
                                shifts = venue_dates_df[venue_dates_df['DATE'] == date]['SHIFT'].unique()
                                date_shifts[date] = list(shifts)
                            
                            # Display date and shift selection
                            st.write("**Select Dates and Shifts:**")
                            
                            # Initialize session state for date selections
                            if 'date_selections' not in st.session_state:
                                st.session_state.date_selections = {}
                            if 'shift_selections' not in st.session_state:
                                st.session_state.shift_selections = {}
                            
                            selected_dates = {}
                            for date in sorted(date_shifts.keys()):
                                col_date, col_shifts = st.columns([1, 3])
                                
                                with col_date:
                                    # Create a unique key for each date checkbox
                                    date_key = f"date_{date.replace('-', '_').replace(' ', '_')}"
                                    if date_key not in st.session_state.date_selections:
                                        st.session_state.date_selections[date_key] = False
                                    
                                    select_date = st.checkbox(
                                        date, 
                                        value=st.session_state.date_selections[date_key],
                                        key=date_key
                                    )
                                    st.session_state.date_selections[date_key] = select_date
                                
                                with col_shifts:
                                    if select_date:
                                        selected_shifts = []
                                        for shift in date_shifts[date]:
                                            # Create a unique key for each shift checkbox
                                            shift_key = f"shift_{date.replace('-', '_').replace(' ', '_')}_{shift.replace(' ', '_')}"
                                            if shift_key not in st.session_state.shift_selections:
                                                st.session_state.shift_selections[shift_key] = True
                                            
                                            select_shift = st.checkbox(
                                                shift,
                                                value=st.session_state.shift_selections[shift_key],
                                                key=shift_key
                                            )
                                            st.session_state.shift_selections[shift_key] = select_shift
                                            
                                            if select_shift:
                                                selected_shifts.append(shift)
                                        
                                        if selected_shifts:
                                            selected_dates[date] = selected_shifts
                            
                            st.session_state.selected_dates = selected_dates
                            
                            # Step 4: IO Selection
                            st.divider()
                            st.subheader("Step 4: Select Centre Coordinator")
                            
                            if st.session_state.io_df is not None and not st.session_state.io_df.empty:
                                # Filter IOs by venue centre code
                                venue_row = venue_dates_df.iloc[0] if not venue_dates_df.empty else None
                                if venue_row is not None and 'CENTRE_CODE' in venue_row:
                                    centre_code = str(venue_row['CENTRE_CODE']).zfill(4)
                                    filtered_io = st.session_state.io_df[
                                        st.session_state.io_df['CENTRE_CODE'].astype(str).str.zfill(4).str.startswith(centre_code[:4])
                                    ]
                                    
                                    if filtered_io.empty:
                                        filtered_io = st.session_state.io_df
                                        st.warning(f"⚠️ No IOs found with matching centre code. Showing all IOs.")
                                else:
                                    filtered_io = st.session_state.io_df
                                
                                # Search box
                                search_term = st.text_input("🔍 Search Centre Coordinator by Name or Area", "")
                                if search_term:
                                    filtered_io = filtered_io[
                                        (filtered_io['NAME'].str.contains(search_term, case=False, na=False)) |
                                        (filtered_io['AREA'].str.contains(search_term, case=False, na=False))
                                    ]
                                
                                if not filtered_io.empty:
                                    # Display IO list with allocation status
                                    io_options = []
                                    io_details = {}
                                    
                                    for _, row in filtered_io.iterrows():
                                        io_name = row['NAME']
                                        area = row['AREA']
                                        centre_code = row.get('CENTRE_CODE', '')
                                        
                                        # Check existing allocations
                                        existing_allocations = [
                                            a for a in st.session_state.allocation 
                                            if a['IO Name'] == io_name and a.get('Exam') == st.session_state.current_exam_key
                                        ]
                                        
                                        status = "🟢 Available"
                                        if existing_allocations:
                                            current_venue_allocations = [
                                                a for a in existing_allocations 
                                                if a['Venue'] == st.session_state.selected_venue and a['Role'] == st.session_state.selected_role
                                            ]
                                            if current_venue_allocations:
                                                status = "🔴 Already allocated here"
                                            else:
                                                status = "🟡 Allocated elsewhere"
                                        
                                        display_text = f"{io_name} ({area}) - {status}"
                                        io_options.append(display_text)
                                        io_details[display_text] = {
                                            'name': io_name,
                                            'area': area,
                                            'centre_code': centre_code,
                                            'status': status
                                        }
                                    
                                    # IO selection dropdown
                                    selected_display = st.selectbox(
                                        "Select Centre Coordinator",
                                        options=io_options,
                                        key="io_selector"
                                    )
                                    
                                    if selected_display:
                                        io_info = io_details[selected_display]
                                        
                                        # Allocation button
                                        if st.button("✅ Allocate Selected IO to Dates", use_container_width=True, type="primary"):
                                            if not selected_dates:
                                                st.error("❌ Please select at least one date and shift")
                                            else:
                                                # Get allocation reference
                                                ref_data = get_allocation_reference(st.session_state.selected_role)
                                                if ref_data:
                                                    # Perform allocation
                                                    allocation_count = 0
                                                    conflicts = []
                                                    
                                                    for date, shifts in selected_dates.items():
                                                        for shift in shifts:
                                                            # Check for conflict
                                                            conflict = check_allocation_conflict(
                                                                io_info['name'], date, shift, 
                                                                st.session_state.selected_venue, 
                                                                st.session_state.selected_role, "IO"
                                                            )
                                                            
                                                            if conflict:
                                                                conflicts.append(conflict)
                                                                continue
                                                            
                                                            # Create allocation
                                                            allocation = {
                                                                'Sl. No.': len(st.session_state.allocation) + 1,
                                                                'Venue': st.session_state.selected_venue,
                                                                'Date': date,
                                                                'Shift': shift,
                                                                'IO Name': io_info['name'],
                                                                'Area': io_info['area'],
                                                                'Role': st.session_state.selected_role,
                                                                'Mock Test': st.session_state.mock_test_mode,
                                                                'Exam': st.session_state.current_exam_key,
                                                                'Order No.': ref_data['order_no'],
                                                                'Page No.': ref_data['page_no'],
                                                                'Reference Remarks': ref_data.get('remarks', '')
                                                            }
                                                            st.session_state.allocation.append(allocation)
                                                            allocation_count += 1
                                                    
                                                    if conflicts:
                                                        st.error(f"❌ Allocation conflicts:\n" + "\n".join(conflicts[:3]))
                                                    
                                                    if allocation_count > 0:
                                                        if save_data():
                                                            st.success(f"✅ Allocated {io_info['name']} to {allocation_count} shift(s)!")
                                                            # Clear date selections
                                                            for key in list(st.session_state.date_selections.keys()):
                                                                st.session_state.date_selections[key] = False
                                                            for key in list(st.session_state.shift_selections.keys()):
                                                                st.session_state.shift_selections[key] = False
                                                            time.sleep(2)
                                                            st.rerun()
                                                        else:
                                                            st.error("❌ Failed to save allocation")
                                                else:
                                                    st.warning("⚠️ Allocation cancelled - no reference provided")
                                else:
                                    st.warning("⚠️ No Centre Coordinators found matching the search criteria")
                            else:
                                st.warning("⚠️ Please load Centre Coordinator master data first")
                        else:
                            st.warning("⚠️ No date information found for selected venue")
                else:
                    st.warning("⚠️ No venues found in the loaded data")
            else:
                st.warning("⚠️ Please load venue data first")
            
            # Display current allocations
            st.divider()
            st.subheader("📋 Current Allocations")
            
            if st.session_state.allocation:
                alloc_df = pd.DataFrame(st.session_state.allocation)
                
                # Display table
                st.dataframe(
                    alloc_df[['Sl. No.', 'Venue', 'Date', 'Shift', 'IO Name', 'Area', 'Role', 'Mock Test']],
                    use_container_width=True,
                    hide_index=True
                )
                
                # Delete options
                col_del1, col_del2 = st.columns(2)
                with col_del1:
                    if st.button("🗑️ Delete Last Entry", use_container_width=True, type="secondary"):
                        if st.session_state.allocation:
                            # Ask for deletion reference
                            del_ref = ask_for_deletion_reference(st.session_state.allocation[-1]['Role'], 1)
                            if del_ref:
                                # Add to deleted records
                                deleted_entry = st.session_state.allocation[-1].copy()
                                deleted_entry['Deletion Reason'] = del_ref['reason']
                                deleted_entry['Deletion Order No.'] = del_ref['order_no']
                                deleted_entry['Deletion Timestamp'] = datetime.now().isoformat()
                                deleted_entry['Type'] = 'IO'
                                st.session_state.deleted_records.append(deleted_entry)
                                
                                st.session_state.allocation.pop()
                                if save_data():
                                    st.success("✅ Last entry deleted!")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to delete entry")
                
                with col_del2:
                    if st.button("🗑️ Bulk Delete", use_container_width=True, type="secondary"):
                        st.warning("Bulk delete feature coming soon")
            else:
                st.info("ℹ️ No allocations yet. Start by allocating Centre Coordinators above.")
    
    # Tab 3: EY Personnel Allocation
    with tab3:
        st.header("👁️ EY Personnel Allocation")
        
        if not st.session_state.current_exam_key:
            st.warning("⚠️ Please select or create an exam first from the Exam Management tab")
        else:
            # Toggle EY mode
            st.session_state.ey_allocation_mode = st.checkbox(
                "Enable EY Personnel Allocation Mode",
                value=st.session_state.ey_allocation_mode,
                key="ey_mode_checkbox"
            )
            
            if st.session_state.ey_allocation_mode:
                col_ey1, col_ey2 = st.columns([2, 1])
                
                with col_ey1:
                    st.subheader("Step 1: Load EY Personnel Master")
                    
                    ey_file = st.file_uploader(
                        "Upload EY Personnel Master (Excel)",
                        type=["xlsx", "xls"],
                        key="ey_master_upload",
                        help="Excel file with NAME column (optional: MOBILE, EMAIL, ID_NUMBER, DESIGNATION, DEPARTMENT)"
                    )
                    
                    if ey_file is not None:
                        try:
                            st.session_state.ey_df = pd.read_excel(ey_file)
                            st.session_state.ey_df.columns = [str(col).strip().upper() for col in st.session_state.ey_df.columns]
                            
                            required_cols = ["NAME"]
                            missing_cols = [col for col in required_cols if col not in st.session_state.ey_df.columns]
                            
                            if missing_cols:
                                st.error(f"❌ Missing required columns: {', '.join(missing_cols)}")
                            else:
                                optional_cols = ["MOBILE", "EMAIL", "ID_NUMBER", "DESIGNATION", "DEPARTMENT"]
                                for col in optional_cols:
                                    if col not in st.session_state.ey_df.columns:
                                        st.session_state.ey_df[col] = ""
                                
                                st.session_state.ey_df['NAME'] = st.session_state.ey_df['NAME'].astype(str).str.strip()
                                st.success(f"✅ Loaded {len(st.session_state.ey_df)} EY Personnel records")
                        except Exception as e:
                            st.error(f"❌ Error loading file: {str(e)}")
                    
                    # EY Rate
                    st.subheader("💰 EY Personnel Rate")
                    st.session_state.remuneration_rates['ey_personnel'] = st.number_input(
                        "Rate per Day (₹)",
                        min_value=0,
                        value=st.session_state.remuneration_rates['ey_personnel'],
                        key="ey_rate_input"
                    )
                    
                    if st.button("💾 Save EY Rate", use_container_width=True):
                        if save_data():
                            st.success("✅ EY rate saved!")
                        else:
                            st.error("❌ Failed to save EY rate")
                
                with col_ey2:
                    st.subheader("Step 2: Configuration")
                    
                    # Select venues for EY allocation
                    if not st.session_state.venue_df.empty:
                        venues = sorted(st.session_state.venue_df['VENUE'].dropna().unique())
                        st.session_state.selected_ey_venues = st.multiselect(
                            "Select Venues for EY Allocation",
                            options=venues,
                            default=st.session_state.selected_ey_venues
                        )
                    
                    if st.button("📍 Select All Venues", use_container_width=True):
                        if not st.session_state.venue_df.empty:
                            venues = sorted(st.session_state.venue_df['VENUE'].dropna().unique())
                            st.session_state.selected_ey_venues = venues
                            st.success(f"✅ Selected all {len(venues)} venues")
                            time.sleep(1)
                            st.rerun()
                
                st.divider()
                
                # Step 3: Select EY Personnel
                st.subheader("Step 3: Select EY Personnel")
                
                if not st.session_state.ey_df.empty:
                    # Search EY personnel
                    ey_search = st.text_input("🔍 Search EY Personnel by Name, Mobile, or Email", "")
                    
                    if ey_search:
                        filtered_ey = st.session_state.ey_df[
                            (st.session_state.ey_df['NAME'].str.contains(ey_search, case=False, na=False)) |
                            (st.session_state.ey_df['MOBILE'].astype(str).str.contains(ey_search, case=False, na=False)) |
                            (st.session_state.ey_df['EMAIL'].str.contains(ey_search, case=False, na=False))
                        ]
                    else:
                        filtered_ey = st.session_state.ey_df
                    
                    if not filtered_ey.empty:
                        # Display EY personnel list
                        ey_options = []
                        ey_details = {}
                        
                        for _, row in filtered_ey.iterrows():
                            name = row['NAME']
                            mobile = row.get('MOBILE', '')
                            email = row.get('EMAIL', '')
                            designation = row.get('DESIGNATION', '')
                            
                            display_text = f"{name}"
                            if mobile:
                                display_text += f" | 📱 {mobile}"
                            if email:
                                display_text += f" | 📧 {email}"
                            if designation:
                                display_text += f" | 👤 {designation}"
                            
                            ey_options.append(display_text)
                            ey_details[display_text] = {
                                'name': name,
                                'mobile': mobile,
                                'email': email,
                                'designation': designation,
                                'id_number': row.get('ID_NUMBER', ''),
                                'department': row.get('DEPARTMENT', '')
                            }
                        
                        selected_ey_display = st.selectbox(
                            "Select EY Personnel",
                            options=ey_options,
                            key="ey_person_selector"
                        )
                        
                        if selected_ey_display:
                            ey_info = ey_details[selected_ey_display]
                            
                            # Step 4: Select Dates
                            st.subheader("Step 4: Select Dates")
                            
                            if not st.session_state.venue_df.empty and st.session_state.selected_ey_venues:
                                # Get unique dates from selected venues
                                all_dates = set()
                                for venue in st.session_state.selected_ey_venues:
                                    venue_dates = st.session_state.venue_df[
                                        st.session_state.venue_df['VENUE'] == venue
                                    ]['DATE'].unique()
                                    all_dates.update(venue_dates)
                                
                                if all_dates:
                                    selected_ey_dates = st.multiselect(
                                        "Select Dates",
                                        options=sorted(all_dates),
                                        default=[],
                                        key="ey_date_selector"
                                    )
                                    
                                    # Get shifts for selected dates
                                    selected_shifts = {}
                                    for date in selected_ey_dates:
                                        shifts = st.multiselect(
                                            f"Shifts for {date}",
                                            options=["Morning", "Afternoon", "Evening"],
                                            default=["Morning", "Afternoon", "Evening"],
                                            key=f"ey_shifts_{date.replace('-', '_')}"
                                        )
                                        if shifts:
                                            selected_shifts[date] = shifts
                                    
                                    # Allocation button
                                    if st.button("✅ Allocate EY Personnel", use_container_width=True, type="primary"):
                                        if not selected_shifts:
                                            st.error("❌ Please select at least one date and shift")
                                        elif not st.session_state.selected_ey_venues:
                                            st.error("❌ Please select at least one venue")
                                        else:
                                            # Get allocation reference
                                            ref_data = get_allocation_reference("EY Personnel")
                                            if ref_data:
                                                # Perform allocation
                                                allocation_count = 0
                                                conflicts = []
                                                
                                                for venue in st.session_state.selected_ey_venues:
                                                    for date, shifts in selected_shifts.items():
                                                        for shift in shifts:
                                                            # Check for conflict
                                                            conflict = check_allocation_conflict(
                                                                ey_info['name'], date, shift, venue, "", "EY"
                                                            )
                                                            
                                                            if conflict:
                                                                conflicts.append(conflict)
                                                                continue
                                                            
                                                            # Create allocation
                                                            allocation = {
                                                                'Sl. No.': len(st.session_state.ey_allocation) + 1,
                                                                'Venue': venue,
                                                                'Date': date,
                                                                'Shift': shift,
                                                                'EY Personnel': ey_info['name'],
                                                                'Mobile': ey_info['mobile'],
                                                                'Email': ey_info['email'],
                                                                'ID Number': ey_info['id_number'],
                                                                'Designation': ey_info['designation'],
                                                                'Department': ey_info['department'],
                                                                'Mock Test': False,
                                                                'Exam': st.session_state.current_exam_key,
                                                                'Rate (₹)': st.session_state.remuneration_rates['ey_personnel'],
                                                                'Order No.': ref_data['order_no'],
                                                                'Page No.': ref_data['page_no'],
                                                                'Reference Remarks': ref_data.get('remarks', '')
                                                            }
                                                            st.session_state.ey_allocation.append(allocation)
                                                            allocation_count += 1
                                                
                                                if conflicts:
                                                    st.error(f"❌ Allocation conflicts:\n" + "\n".join(conflicts[:3]))
                                                
                                                if allocation_count > 0:
                                                    if save_data():
                                                        st.success(f"✅ Allocated {ey_info['name']} to {allocation_count} shift(s) across {len(st.session_state.selected_ey_venues)} venue(s)!")
                                                        time.sleep(2)
                                                        st.rerun()
                                                    else:
                                                        st.error("❌ Failed to save allocation")
                                            else:
                                                st.warning("⚠️ Allocation cancelled - no reference provided")
                                else:
                                    st.warning("⚠️ No dates found for selected venues")
                            else:
                                st.warning("⚠️ Please select venues first")
                    else:
                        st.warning("⚠️ No EY personnel found matching search criteria")
                else:
                    st.warning("⚠️ Please load EY Personnel master data first")
                
                # Display EY allocations
                st.divider()
                st.subheader("📋 Current EY Allocations")
                
                if st.session_state.ey_allocation:
                    ey_alloc_df = pd.DataFrame(st.session_state.ey_allocation)
                    st.dataframe(
                        ey_alloc_df[['Sl. No.', 'Venue', 'Date', 'Shift', 'EY Personnel', 'Mobile', 'Email', 'Designation']],
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    col_del1, col_del2 = st.columns(2)
                    with col_del1:
                        if st.button("🗑️ Delete Last EY Entry", use_container_width=True, type="secondary", key="del_last_ey"):
                            if st.session_state.ey_allocation:
                                # Ask for deletion reference
                                del_ref = ask_for_deletion_reference("EY Personnel", 1)
                                if del_ref:
                                    # Add to deleted records
                                    deleted_entry = st.session_state.ey_allocation[-1].copy()
                                    deleted_entry['Deletion Reason'] = del_ref['reason']
                                    deleted_entry['Deletion Order No.'] = del_ref['order_no']
                                    deleted_entry['Deletion Timestamp'] = datetime.now().isoformat()
                                    deleted_entry['Type'] = 'EY Personnel'
                                    st.session_state.deleted_records.append(deleted_entry)
                                    
                                    st.session_state.ey_allocation.pop()
                                    if save_data():
                                        st.success("✅ Last EY entry deleted!")
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        st.error("❌ Failed to delete EY entry")
                    
                    with col_del2:
                        if st.button("🗑️ Bulk Delete EY", use_container_width=True, type="secondary"):
                            st.warning("Bulk delete feature coming soon")
                else:
                    st.info("ℹ️ No EY allocations yet. Start by allocating EY Personnel above.")
            else:
                st.info("ℹ️ Enable EY Personnel Allocation Mode to allocate EY personnel")
    
    # Tab 4: Reports & Export
    with tab4:
        st.header("📊 Reports & Export")
        
        if not st.session_state.current_exam_key:
            st.warning("⚠️ Please select or create an exam first")
        else:
            col_report1, col_report2 = st.columns(2)
            
            with col_report1:
                st.subheader("📈 Export Options")
                
                if st.button("📊 Export Allocations Report", use_container_width=True, type="primary"):
                    export_allocations_report()
                
                if st.button("💰 Export Remuneration Report", use_container_width=True, type="primary"):
                    export_remuneration_report()
            
            with col_report2:
                st.subheader("📊 Quick Reports")
                
                if st.button("👥 Centre Coordinator Summary", use_container_width=True):
                    show_io_summary()
                
                if st.button("👁️ EY Personnel Summary", use_container_width=True):
                    show_ey_summary()
                
                if st.button("📅 Date-wise Summary", use_container_width=True):
                    show_date_summary()
            
            st.divider()
            
            # Current Statistics
            st.subheader("📊 Current Statistics")
            
            col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
            
            with col_stat1:
                total_io = len(st.session_state.allocation)
                st.metric("Centre Coordinator Allocations", total_io)
            
            with col_stat2:
                total_ey = len(st.session_state.ey_allocation)
                st.metric("EY Personnel Allocations", total_ey)
            
            with col_stat3:
                if st.session_state.allocation:
                    unique_ios = len(set(a['IO Name'] for a in st.session_state.allocation))
                    st.metric("Unique Centre Coordinators", unique_ios)
                else:
                    st.metric("Unique Centre Coordinators", 0)
            
            with col_stat4:
                if st.session_state.ey_allocation:
                    unique_ey = len(set(a['EY Personnel'] for a in st.session_state.ey_allocation))
                    st.metric("Unique EY Personnel", unique_ey)
                else:
                    st.metric("Unique EY Personnel", 0)
    
    # Tab 5: Settings
    with tab5:
        st.header("⚙️ Settings")
        
        tab_settings, tab_backup, tab_help = st.tabs(["⚙️ Settings", "💾 Backup", "❓ Help"])
        
        with tab_settings:
            st.subheader("🌐 GitHub Configuration")
            
            if GITHUB_TOKEN:
                st.success("✅ GitHub token configured")
                st.info(f"**Repository:** {GITHUB_OWNER}/{GITHUB_REPO}")
                st.info(f"**Branch:** {GITHUB_BRANCH}")
                
                if st.session_state.github_connected:
                    st.success("✅ Connected to GitHub")
                else:
                    st.error("❌ Not connected to GitHub")
            else:
                st.error("❌ GitHub token not configured")
                st.info("""
                **Setup Required:**
                1. Create a private GitHub repository
                2. Generate a Personal Access Token with 'repo' scope
                3. Add secrets to `.streamlit/secrets.toml`:
                ```
                GITHUB_OWNER = "your_github_username"
                GITHUB_REPO = "cc_fso_allocation_data"
                GITHUB_TOKEN = "your_token_here"
                ```
                """)
            
            st.divider()
            st.subheader("🗃️ Data Management")
            
            col_set1, col_set2 = st.columns(2)
            
            with col_set1:
                if st.button("🔄 Reset Current Exam", use_container_width=True, type="secondary"):
                    if st.session_state.current_exam_key:
                        st.warning(f"⚠️ This will reset all allocations for '{st.session_state.current_exam_key}'!")
                        confirm = st.checkbox("I confirm I want to reset this exam")
                        if confirm:
                            st.session_state.allocation = []
                            st.session_state.ey_allocation = []
                            if save_data():
                                st.success("✅ Exam data reset successfully!")
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("❌ Failed to reset exam data")
                    else:
                        st.warning("⚠️ No exam selected")
            
            with col_set2:
                if st.button("🗑️ Clear Deleted Records", use_container_width=True, type="secondary"):
                    st.warning("⚠️ This will clear ALL deleted records!")
                    confirm = st.checkbox("I confirm I want to clear ALL deleted records")
                    if confirm:
                        st.session_state.deleted_records = []
                        if save_data():
                            st.success("✅ Deleted records cleared!")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Failed to clear deleted records")
            
            st.divider()
            st.subheader("💻 System Information")
            
            info_col1, info_col2 = st.columns(2)
            
            with info_col1:
                st.write("**📁 GitHub Files:**")
                
                # Check each file
                files_to_check = [
                    ("config.json", CONFIG_FILE_PATH),
                    ("allocations_data.json", DATA_FILE_PATH),
                    ("allocation_references.json", REFERENCE_FILE_PATH),
                    ("deleted_records.json", DELETED_FILE_PATH)
                ]
                
                for display_name, file_path in files_to_check:
                    data = load_from_github(file_path)
                    if data is not None:
                        st.write(f"- {display_name}: ✅ Exists")
                    else:
                        st.write(f"- {display_name}: ❌ Not found")
            
            with info_col2:
                st.write("**📊 Current Data:**")
                st.write(f"- Exams: {len(st.session_state.exam_data)}")
                st.write(f"- IO Allocations: {len(st.session_state.allocation)}")
                st.write(f"- EY Allocations: {len(st.session_state.ey_allocation)}")
                st.write(f"- Deleted Records: {len(st.session_state.deleted_records)}")
                st.write(f"- Allocation References: {sum(len(refs) for refs in st.session_state.allocation_references.values())}")
        
        with tab_backup:
            st.subheader("💾 Backup & Restore")
            
            col_back1, col_back2 = st.columns(2)
            
            with col_back1:
                if st.button("💾 Create Backup", use_container_width=True, type="primary"):
                    try:
                        # Create a backup by saving current state to a backup file
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        backup_data = {
                            'exam_data': st.session_state.exam_data,
                            'allocation_references': st.session_state.allocation_references,
                            'deleted_records': st.session_state.deleted_records,
                            'config': {
                                'remuneration_rates': st.session_state.remuneration_rates,
                                'ey_personnel_list': st.session_state.ey_personnel_list
                            },
                            'backup_timestamp': timestamp
                        }
                        
                        backup_file = f"backup_{timestamp}.json"
                        if save_to_github(f"backups/{backup_file}", backup_data):
                            st.success(f"✅ Backup created: {backup_file}")
                        else:
                            st.error("❌ Failed to create backup")
                    except Exception as e:
                        st.error(f"❌ Error creating backup: {str(e)}")
                
                # List existing backups
                st.write("**📂 Available Backups:**")
                st.info("Backups are stored in the 'backups' folder of your GitHub repository")
            
            with col_back2:
                if st.button("🔄 Sync with GitHub", use_container_width=True, type="secondary"):
                    load_data()
                    st.success("✅ Synced with GitHub!")
                    time.sleep(1)
                    st.rerun()
                
                if st.button("📤 Export All Data", use_container_width=True):
                    try:
                        # Create a comprehensive export
                        all_data = {
                            'exam_data': st.session_state.exam_data,
                            'allocation_references': st.session_state.allocation_references,
                            'deleted_records': st.session_state.deleted_records,
                            'config': {
                                'remuneration_rates': st.session_state.remuneration_rates,
                                'ey_personnel_list': st.session_state.ey_personnel_list
                            },
                            'export_timestamp': datetime.now().isoformat()
                        }
                        
                        # Convert to JSON
                        json_data = json.dumps(all_data, indent=4, ensure_ascii=False, default=str)
                        
                        # Offer download
                        filename = f"full_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                        st.download_button(
                            label="📥 Download Full Export",
                            data=json_data,
                            file_name=filename,
                            mime="application/json",
                            use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"❌ Export failed: {str(e)}")
        
        with tab_help:
            st.subheader("❓ Help & Documentation")
            
            st.markdown("""
            ### 📖 User Guide
            
            **1. 📋 Exam Management**
            - Create a new exam by entering Exam Name and Year
            - Select existing exams from the dropdown
            - Set allocation references for each role (Order No., Page No.)
            
            **2. 👥 Centre Coordinator Allocation**
            - Load Centre Coordinator master file (Excel format)
            - Load Venue list file (Excel format)
            - Select venue, dates, and shifts
            - Search and select Centre Coordinators
            - Allocate with proper references
            
            **3. 👁️ EY Personnel Allocation**
            - Load EY Personnel master file (Excel format)
            - Enable EY allocation mode
            - Select multiple venues and dates
            - Allocate EY personnel with references
            
            **4. 📊 Reports & Export**
            - Export allocation reports in Excel format
            - Generate remuneration reports
            - View summary statistics
            
            **5. ⚙️ Settings & Tools**
            - GitHub configuration
            - Backup and restore data
            - View allocation references
            - View deleted records
            
            ### 🌐 GitHub Storage
            
            **All data is stored in your private GitHub repository:**
            - `config.json`: Remuneration rates and EY personnel list
            - `allocations_data.json`: All exam allocations
            - `allocation_references.json`: Order and page references
            - `deleted_records.json`: Deleted allocations with reasons
            
            ### 📝 Data Format Requirements
            
            **Centre Coordinator Master File (Excel)**
            Required columns:
            - `NAME`: Name of Centre Coordinator
            - `AREA`: Area/Region
            - `CENTRE_CODE`: Centre code (4 digits)
            
            **Venue List File (Excel)**
            Required columns:
            - `VENUE`: Venue name
            - `DATE`: Date of allocation (DD-MM-YYYY)
            - `SHIFT`: Shift (Morning/Afternoon/Evening or BATCH-1, etc.)
            - `CENTRE_CODE`: Centre code
            - `ADDRESS`: Venue address
            
            **EY Personnel Master File (Excel)**
            Required columns:
            - `NAME`: Name of EY Personnel
            
            Optional columns:
            - `MOBILE`: Mobile number
            - `EMAIL`: Email address
            - `ID_NUMBER`: ID number
            - `DESIGNATION`: Designation
            - `DEPARTMENT`: Department
            
            ### ⚠️ Important Notes
            
            - **GitHub Repository**: Must be **private** for security
            - **Personal Access Token**: Requires 'repo' scope
            - **Data Sync**: Click 'Save All Data' to sync changes to GitHub
            - **Backups**: Regular backups are recommended
            - **References**: Always set allocation references before allocating
            
            ### 🆘 Support
            
            For issues or questions, please contact the system administrator.
            
            ---
            
            **Designed by Bijay Paswan**  
            **Version 2.0 (GitHub Integration)**  
            **Staff Selection Commission (ER), Kolkata**  
            © All rights reserved
            """)

if __name__ == "__main__":
    main()
