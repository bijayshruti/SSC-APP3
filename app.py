"""
STAFF SELECTION COMMISSION (ER), KOLKATA
Centre Coordinator & Flying Squad Allocation System
Streamlit Web Application
Designed by Bijay Paswan

ENHANCED VERSION WITH COMPREHENSIVE DELETION & RECORD MANAGEMENT SYSTEM
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import sys
import logging
import warnings
import hashlib
import base64
from io import BytesIO, StringIO
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Set
import traceback
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, numbers
from openpyxl.utils import get_column_letter

warnings.filterwarnings('ignore')

# ============================================================================
# CONSTANTS AND CONFIGURATION
# ============================================================================

# Create necessary directories
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
BACKUP_DIR = DATA_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)
AUDIT_DIR = DATA_DIR / "audit_logs"
AUDIT_DIR.mkdir(exist_ok=True)

# File paths
CONFIG_FILE = DATA_DIR / "config.json"
DATA_FILE = DATA_DIR / "allocations_data.json"
REFERENCE_FILE = DATA_DIR / "allocation_references.json"
DELETED_RECORDS_FILE = DATA_DIR / "deleted_records.json"
AUDIT_LOG_FILE = AUDIT_DIR / f"audit_{datetime.now().strftime('%Y%m')}.json"
LOGFILE = DATA_DIR / "app.log"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=LOGFILE
)

# Default remuneration rates
DEFAULT_RATES = {
    'multiple_shifts': 750,
    'single_shift': 450,
    'mock_test': 450,
    'ey_personnel': 5000
}

# ============================================================================
# SESSION STATE MANAGEMENT - COMPLETE INITIALIZATION
# ============================================================================

def initialize_session_state():
    """Initialize all session state variables"""
    # Data storage
    default_values = {
        'io_df': pd.DataFrame(),
        'venue_df': pd.DataFrame(),
        'ey_df': pd.DataFrame(),
        'allocation': [],
        'ey_allocation': [],
        'deleted_records': [],
        'undo_stack': [],
        'redo_stack': [],
        
        # Configuration
        'remuneration_rates': DEFAULT_RATES.copy(),
        'exam_data': {},
        'allocation_references': {},
        
        # Current state
        'current_exam_key': "",
        'exam_name': "",
        'exam_year': "",
        'mock_test_mode': False,
        'ey_allocation_mode': False,
        
        # UI state
        'selected_venue': "",
        'selected_role': "Centre Coordinator",
        'selected_dates': [],
        'selected_io': "",
        'selected_ey': "",
        
        # Enhanced Date Selection System
        'date_grid_state': {
            'normal_dates': {},
            'mock_dates': {},
            'ey_dates': {},
            'expanded_dates': {},
            'select_all': False
        },
        'date_grid_mode': "IO",
        'conflict_warning': None,
        
        # File upload tracking
        'io_master_loaded': False,
        'venue_master_loaded': False,
        'ey_master_loaded': False,
        
        # Current allocation state
        'current_allocation_person': None,
        'current_allocation_area': None,
        'current_allocation_role': None,
        'current_allocation_type': None,
        'current_allocation_ey_row': None,
        
        # UI flags
        'show_io_upload': False,
        'show_venue_upload': False,
        'show_ey_upload': False,
        'creating_new_ref_IO': False,
        'creating_new_ref_EY Personnel': False,
        
        # Current menu
        'menu': 'dashboard',
        
        # Deletion system state
        'deletion_mode': None,
        'selected_deletions': [],
        'bulk_deletion_role_groups': {},
        'show_deletion_dialog': False,
        'deletion_order_no': "",
        'deletion_reason': "",
        'show_deleted_records': False,
        'deleted_records_filter': "all",
        'show_bulk_delete': False,
        'bulk_delete_selection': [],
        'last_action': None,
        'show_update_reference': False,
        'update_reference_data': None
    }
    
    # Initialize all values
    for key, default_value in default_values.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

# ============================================================================
# AUDIT LOGGING SYSTEM
# ============================================================================

def log_audit_event(event_type: str, event_data: Dict, user_action: str = ""):
    """Log audit events for compliance"""
    try:
        audit_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'event_data': event_data,
            'user_action': user_action,
            'exam': st.session_state.current_exam_key,
            'user': "system_admin"  # In production, replace with actual user
        }
        
        # Load existing audit log
        audit_log = []
        if AUDIT_LOG_FILE.exists():
            with open(AUDIT_LOG_FILE, 'r') as f:
                audit_log = json.load(f)
        
        # Append new entry
        audit_log.append(audit_entry)
        
        # Save audit log
        with open(AUDIT_LOG_FILE, 'w') as f:
            json.dump(audit_log, f, indent=2, default=str)
        
        return True
    except Exception as e:
        logging.error(f"Audit logging error: {str(e)}")
        return False

# ============================================================================
# DATA PERSISTENCE FUNCTIONS
# ============================================================================

def load_all_data():
    """Load all data from files"""
    try:
        # Load config
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                st.session_state.remuneration_rates = config.get('remuneration_rates', DEFAULT_RATES.copy())
        
        # Load exam data
        if DATA_FILE.exists():
            with open(DATA_FILE, 'r') as f:
                exam_data = json.load(f)
                st.session_state.exam_data = {}
                for exam_key, data in exam_data.items():
                    if isinstance(data, dict):
                        st.session_state.exam_data[exam_key] = data
                    else:
                        st.session_state.exam_data[exam_key] = {
                            'io_allocations': data,
                            'ey_allocations': []
                        }
        
        # Load reference data
        if REFERENCE_FILE.exists():
            with open(REFERENCE_FILE, 'r') as f:
                ref_data = json.load(f)
                st.session_state.allocation_references = ref_data
        
        # Load deleted records
        if DELETED_RECORDS_FILE.exists():
            with open(DELETED_RECORDS_FILE, 'r') as f:
                deleted_data = json.load(f)
                st.session_state.deleted_records = deleted_data
        
        # Load current allocations
        if st.session_state.current_exam_key and st.session_state.current_exam_key in st.session_state.exam_data:
            exam_data = st.session_state.exam_data[st.session_state.current_exam_key]
            st.session_state.allocation = exam_data.get('io_allocations', [])
            st.session_state.ey_allocation = exam_data.get('ey_allocations', [])
        
        return True
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return False

def save_all_data():
    """Save all data to files"""
    try:
        # Update current exam data before saving
        if st.session_state.current_exam_key:
            if st.session_state.current_exam_key not in st.session_state.exam_data:
                st.session_state.exam_data[st.session_state.current_exam_key] = {
                    'io_allocations': [],
                    'ey_allocation': []
                }
            
            # Update allocations for current exam
            st.session_state.exam_data[st.session_state.current_exam_key]['io_allocations'] = st.session_state.allocation
            st.session_state.exam_data[st.session_state.current_exam_key]['ey_allocations'] = st.session_state.ey_allocation
        
        # Save config
        config = {
            'remuneration_rates': st.session_state.remuneration_rates,
            'last_saved': datetime.now().isoformat()
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4, default=str)
        
        # Save exam data
        with open(DATA_FILE, 'w') as f:
            json.dump(st.session_state.exam_data, f, indent=4, default=str)
        
        # Save reference data
        with open(REFERENCE_FILE, 'w') as f:
            json.dump(st.session_state.allocation_references, f, indent=4, default=str)
        
        # Save deleted records
        with open(DELETED_RECORDS_FILE, 'w') as f:
            json.dump(st.session_state.deleted_records, f, indent=4, default=str)
        
        return True
    except Exception as e:
        st.error(f"Error saving data: {str(e)}")
        return False

# ============================================================================
# BACKUP MANAGEMENT
# ============================================================================

def create_backup(description=""):
    """Create a backup of current data"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}"
        if description:
            backup_name += f"_{description.replace(' ', '_')}"
        backup_file = BACKUP_DIR / f"{backup_name}.json"
        
        backup_data = {
            'timestamp': datetime.now().isoformat(),
            'description': description,
            'exam_data': st.session_state.exam_data,
            'allocation_references': st.session_state.allocation_references,
            'remuneration_rates': st.session_state.remuneration_rates,
            'deleted_records': st.session_state.deleted_records,
            'current_exam_key': st.session_state.current_exam_key
        }
        
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=4, default=str)
        
        # Log backup creation
        log_audit_event(
            event_type="backup_created",
            event_data={
                "backup_file": backup_file.name,
                "description": description,
                "record_count": {
                    "exams": len(st.session_state.exam_data),
                    "deleted_records": len(st.session_state.deleted_records)
                }
            },
            user_action="System backup"
        )
        
        return backup_file
    except Exception as e:
        return None

def restore_from_backup(backup_file):
    """Restore data from backup file"""
    try:
        with open(backup_file, 'r') as f:
            backup_data = json.load(f)
        
        # Save current state to undo stack
        current_state = {
            'exam_data': st.session_state.exam_data.copy(),
            'allocation_references': st.session_state.allocation_references.copy(),
            'deleted_records': st.session_state.deleted_records.copy(),
            'current_exam_key': st.session_state.current_exam_key
        }
        st.session_state.undo_stack.append(current_state)
        
        # Restore data
        st.session_state.exam_data = backup_data.get('exam_data', {})
        st.session_state.allocation_references = backup_data.get('allocation_references', {})
        st.session_state.remuneration_rates = backup_data.get('remuneration_rates', DEFAULT_RATES.copy())
        st.session_state.deleted_records = backup_data.get('deleted_records', [])
        st.session_state.current_exam_key = backup_data.get('current_exam_key', "")
        
        # Clear current allocations
        st.session_state.allocation = []
        st.session_state.ey_allocation = []
        
        # Load allocations if exam key exists
        if st.session_state.current_exam_key and st.session_state.current_exam_key in st.session_state.exam_data:
            exam_data = st.session_state.exam_data[st.session_state.current_exam_key]
            st.session_state.allocation = exam_data.get('io_allocations', [])
            st.session_state.ey_allocation = exam_data.get('ey_allocations', [])
        
        # Save restored data
        save_all_data()
        
        # Log restoration
        log_audit_event(
            event_type="backup_restored",
            event_data={
                "backup_file": backup_file.name,
                "description": backup_data.get('description', ''),
                "timestamp": backup_data.get('timestamp', '')
            },
            user_action="Restored from backup"
        )
        
        return True
    except Exception as e:
        return False

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def load_default_master_data():
    """Load default master data for demonstration"""
    # Default IO data
    default_io_data = {
        'NAME': [
            'John Doe', 'Jane Smith', 'Robert Johnson', 
            'Emily Davis', 'Michael Wilson', 'Sarah Brown',
            'David Miller', 'Lisa Anderson', 'James Taylor',
            'Maria Thomas'
        ],
        'AREA': [
            'Kolkata', 'Howrah', 'Hooghly', 'Nadia', 
            'North 24 Parganas', 'South 24 Parganas',
            'Bardhaman', 'Birbhum', 'Bankura', 'Purulia'
        ],
        'CENTRE_CODE': ['1001', '1002', '1003', '2001', '2002', '3001', '3002', '4001', '4002', '5001'],
        'MOBILE': [
            '9876543210', '9876543211', '9876543212', '9876543213', '9876543214',
            '9876543215', '9876543216', '9876543217', '9876543218', '9876543219'
        ],
        'EMAIL': [
            'john@example.com', 'jane@example.com', 'robert@example.com',
            'emily@example.com', 'michael@example.com', 'sarah@example.com',
            'david@example.com', 'lisa@example.com', 'james@example.com',
            'maria@example.com'
        ],
        'DESIGNATION': [
            'Assistant Commissioner', 'Deputy Commissioner', 'Assistant Commissioner',
            'Section Officer', 'Assistant Section Officer', 'Section Officer',
            'Deputy Commissioner', 'Assistant Commissioner', 'Section Officer',
            'Assistant Section Officer'
        ],
        'BANK_NAME': ['SBI', 'PNB', 'BOB', 'SBI', 'PNB', 'BOB', 'SBI', 'PNB', 'BOB', 'SBI'],
        'ACCOUNT_NUMBER': ['1234567890', '2345678901', '3456789012', '4567890123', '5678901234',
                          '6789012345', '7890123456', '8901234567', '9012345678', '0123456789'],
        'IFSC_CODE': ['SBIN0001234', 'PNBN0012345', 'BARB0XXXXXX', 'SBIN0001234', 'PNBN0012345',
                     'BARB0XXXXXX', 'SBIN0001234', 'PNBN0012345', 'BARB0XXXXXX', 'SBIN0001234']
    }
    
    st.session_state.io_df = pd.DataFrame(default_io_data)
    st.session_state.io_master_loaded = True
    
    # Default venue data with dates for testing
    venues = ['Kolkata Main Centre', 'Howrah Centre', 'Hooghly Centre']
    venue_data = []
    
    for venue_idx, venue_name in enumerate(venues):
        centre_code = f'100{venue_idx + 1}'
        for day_offset in range(5):  # 5 days
            date = datetime.now().date() + timedelta(days=day_offset)
            date_str = date.strftime("%d-%m-%Y")
            for shift in ['Morning', 'Afternoon', 'Evening']:
                venue_data.append({
                    'VENUE': str(venue_name),
                    'DATE': str(date_str),
                    'SHIFT': str(shift),
                    'CENTRE_CODE': str(centre_code),
                    'ADDRESS': f'Address for {venue_name}',
                    'CENTRE NAME': str(venue_name),
                    'STATE': 'West Bengal',
                    'DISTRICT': str(venue_name.split()[0]),
                    'CAPACITY': 500 + (venue_idx * 100)
                })
    
    st.session_state.venue_df = pd.DataFrame(venue_data)
    st.session_state.venue_master_loaded = True
    
    # Default EY data
    default_ey_data = {
        'NAME': [
            'Dr. Amit Sharma', 'Prof. Priya Gupta', 'Ms. Anjali Chatterjee',
            'Mr. Rajesh Banerjee', 'Dr. Sunita Das', 'Prof. Ravi Kumar'
        ],
        'MOBILE': [
            '9876543201', '9876543202', '9876543203', '9876543204', '9876543205',
            '9876543206'
        ],
        'EMAIL': [
            'sharma@example.com', 'gupta@example.com', 'chatterjee@example.com',
            'banerjee@example.com', 'das@example.com', 'kumar@example.com'
        ],
        'ID_NUMBER': [f'EY00{i+1}' for i in range(6)],
        'DESIGNATION': [
            'Professor', 'Associate Professor', 'Assistant Professor',
            'Lecturer', 'Professor', 'Associate Professor'
        ],
        'DEPARTMENT': [
            'Mathematics', 'Physics', 'Chemistry', 'English',
            'History', 'Computer Science'
        ],
        'UNIVERSITY': [
            'University of Calcutta', 'Jadavpur University', 'Presidency University',
            'University of Calcutta', 'Jadavpur University', 'Presidency University'
        ]
    }
    
    st.session_state.ey_df = pd.DataFrame(default_ey_data)
    st.session_state.ey_master_loaded = True
    
    st.success("Default master data loaded successfully!")

# ============================================================================
# DELETION SYSTEM - TIER 1: SINGLE ENTRY DELETION
# ============================================================================

def show_deletion_dialog(record, record_type="IO"):
    """Show deletion dialog for single entry"""
    
    st.markdown("### 🗑️ Delete Entry")
    
    # Display record info
    if record_type == "IO":
        st.write(f"**IO Name:** {record.get('IO Name', 'N/A')}")
        st.write(f"**Venue:** {record.get('Venue', 'N/A')}")
        st.write(f"**Date:** {record.get('Date', 'N/A')}")
        st.write(f"**Shift:** {record.get('Shift', 'N/A')}")
        st.write(f"**Role:** {record.get('Role', 'N/A')}")
    else:
        st.write(f"**EY Personnel:** {record.get('EY Personnel', 'N/A')}")
        st.write(f"**Venue:** {record.get('Venue', 'N/A')}")
        st.write(f"**Date:** {record.get('Date', 'N/A')}")
        st.write(f"**Shift:** {record.get('Shift', 'N/A')}")
    
    # Deletion reference inputs
    st.markdown("---")
    st.markdown("### 📋 Deletion Reference (Mandatory)")
    
    deletion_order_no = st.text_input(
        "Deletion Order No.:",
        placeholder="e.g., SSC/Deletion/2024/001",
        key="deletion_order_no"
    )
    
    deletion_reason = st.text_area(
        "Deletion Reason:",
        placeholder="Explain why this allocation is being deleted...",
        height=100,
        key="deletion_reason"
    )
    
    col_confirm, col_cancel = st.columns(2)
    
    with col_confirm:
        if st.button("✅ Confirm Deletion", type="primary", use_container_width=True):
            if not deletion_order_no.strip():
                st.error("❌ Deletion Order No. is required")
                return False
            if not deletion_reason.strip():
                st.error("❌ Deletion Reason is required")
                return False
            
            # Save to undo stack
            if record_type == "IO":
                undo_data = {
                    'action': 'delete_io',
                    'record': record.copy(),
                    'record_type': 'IO'
                }
            else:
                undo_data = {
                    'action': 'delete_ey',
                    'record': record.copy(),
                    'record_type': 'EY'
                }
            st.session_state.undo_stack.append(undo_data)
            
            # Perform deletion
            success = delete_single_entry(record, record_type, deletion_order_no, deletion_reason)
            
            if success:
                st.session_state.show_deletion_dialog = False
                st.session_state.deletion_mode = None
                st.rerun()
            return success
    
    with col_cancel:
        if st.button("❌ Cancel", type="secondary", use_container_width=True):
            st.session_state.show_deletion_dialog = False
            st.session_state.deletion_mode = None
            st.rerun()
    
    return False

def delete_single_entry(record, record_type, deletion_order_no, deletion_reason):
    """Delete single entry with audit trail"""
    
    try:
        # Create deletion record
        deletion_record = {
            'original_data': record,
            'deletion_order_no': deletion_order_no.strip(),
            'deletion_reason': deletion_reason.strip(),
            'deletion_timestamp': datetime.now().isoformat(),
            'exam': st.session_state.current_exam_key,
            'record_type': record_type,
            'deleted_by': 'system_admin'
        }
        
        # Add to deleted records
        st.session_state.deleted_records.append(deletion_record)
        
        # Remove from active allocations
        if record_type == "IO":
            # Remove by finding exact match
            for idx, alloc in enumerate(st.session_state.allocation):
                if (alloc.get('Sl. No.') == record.get('Sl. No.') and
                    alloc.get('IO Name') == record.get('IO Name') and
                    alloc.get('Venue') == record.get('Venue') and
                    alloc.get('Date') == record.get('Date') and
                    alloc.get('Shift') == record.get('Shift')):
                    
                    del st.session_state.allocation[idx]
                    
                    # Renumber serial numbers
                    for i, alloc in enumerate(st.session_state.allocation):
                        alloc['Sl. No.'] = i + 1
                    
                    break
        else:
            # EY allocation deletion
            for idx, alloc in enumerate(st.session_state.ey_allocation):
                if (alloc.get('Sl. No.') == record.get('Sl. No.') and
                    alloc.get('EY Personnel') == record.get('EY Personnel') and
                    alloc.get('Venue') == record.get('Venue') and
                    alloc.get('Date') == record.get('Date') and
                    alloc.get('Shift') == record.get('Shift')):
                    
                    del st.session_state.ey_allocation[idx]
                    
                    # Renumber serial numbers
                    for i, alloc in enumerate(st.session_state.ey_allocation):
                        alloc['Sl. No.'] = i + 1
                    
                    break
        
        # Update exam data
        exam_key = st.session_state.current_exam_key
        if exam_key in st.session_state.exam_data:
            st.session_state.exam_data[exam_key]['io_allocations'] = st.session_state.allocation
            st.session_state.exam_data[exam_key]['ey_allocations'] = st.session_state.ey_allocation
        
        # Save data
        save_all_data()
        
        # Log audit event
        log_audit_event(
            event_type="single_entry_deletion",
            event_data={
                "record_type": record_type,
                "record_id": record.get('Sl. No.', 'Unknown'),
                "person_name": record.get('IO Name') or record.get('EY Personnel', 'Unknown'),
                "deletion_order_no": deletion_order_no,
                "reason": deletion_reason[:100]  # Truncate for logging
            },
            user_action="Deleted single entry"
        )
        
        st.success(f"✅ Entry deleted successfully. Deletion Order: {deletion_order_no}")
        return True
        
    except Exception as e:
        st.error(f"❌ Error deleting entry: {str(e)}")
        return False

# ============================================================================
# DELETION SYSTEM - TIER 2: BULK DELETION
# ============================================================================

def show_bulk_delete_interface():
    """Show bulk deletion interface"""
    
    st.markdown("### 🗑️ Bulk Delete - Multiple Entries")
    
    # Search and filter options
    col_search1, col_search2, col_search3 = st.columns(3)
    
    with col_search1:
        search_name = st.text_input("Search by Name:", placeholder="Name contains...")
    
    with col_search2:
        search_venue = st.text_input("Search by Venue:", placeholder="Venue contains...")
    
    with col_search3:
        search_date = st.date_input("Filter by Date:")
    
    # Type filter
    record_type = st.radio(
        "Record Type:",
        ["All", "IO Allocations", "EY Allocations"],
        horizontal=True
    )
    
    # Get allocations based on filters
    all_allocations = []
    
    if record_type in ["All", "IO Allocations"]:
        for alloc in st.session_state.allocation:
            if alloc.get('Exam') == st.session_state.current_exam_key:
                all_allocations.append({
                    'record': alloc,
                    'type': 'IO',
                    'display': f"👨‍💼 {alloc.get('IO Name', 'N/A')} - {alloc.get('Venue', 'N/A')} - {alloc.get('Date', 'N/A')} ({alloc.get('Shift', 'N/A')})"
                })
    
    if record_type in ["All", "EY Allocations"]:
        for alloc in st.session_state.ey_allocation:
            if alloc.get('Exam') == st.session_state.current_exam_key:
                all_allocations.append({
                    'record': alloc,
                    'type': 'EY',
                    'display': f"👁️ {alloc.get('EY Personnel', 'N/A')} - {alloc.get('Venue', 'N/A')} - {alloc.get('Date', 'N/A')} ({alloc.get('Shift', 'N/A')})"
                })
    
    # Apply filters
    filtered_allocations = all_allocations
    
    if search_name:
        filtered_allocations = [
            a for a in filtered_allocations 
            if search_name.lower() in str(a['record'].get('IO Name') or a['record'].get('EY Personnel', '')).lower()
        ]
    
    if search_venue:
        filtered_allocations = [
            a for a in filtered_allocations 
            if search_venue.lower() in str(a['record'].get('Venue', '')).lower()
        ]
    
    if search_date:
        date_str = search_date.strftime("%d-%m-%Y")
        filtered_allocations = [
            a for a in filtered_allocations 
            if str(a['record'].get('Date', '')) == date_str
        ]
    
    if not filtered_allocations:
        st.info("No allocations match your search criteria")
        return
    
    # Multi-select for bulk deletion
    st.markdown(f"**Found {len(filtered_allocations)} allocation(s)**")
    
    # Create checkboxes for selection
    selected_indices = []
    for idx, alloc in enumerate(filtered_allocations):
        if st.checkbox(alloc['display'], key=f"bulk_select_{idx}"):
            selected_indices.append(idx)
    
    if selected_indices:
        st.success(f"✅ Selected {len(selected_indices)} allocation(s) for deletion")
        
        # Group by role/type for separate references
        st.session_state.bulk_deletion_role_groups = {}
        for idx in selected_indices:
            alloc = filtered_allocations[idx]
            record_type = alloc['type']
            
            if record_type == 'IO':
                role = alloc['record'].get('Role', 'Unknown')
                group_key = f"IO_{role}"
            else:
                group_key = "EY"
            
            if group_key not in st.session_state.bulk_deletion_role_groups:
                st.session_state.bulk_deletion_role_groups[group_key] = []
            
            st.session_state.bulk_deletion_role_groups[group_key].append(alloc['record'])
        
        # Show role groups
        st.markdown("#### 📊 Deletion Groups (by Role)")
        for group_key, records in st.session_state.bulk_deletion_role_groups.items():
            st.write(f"**{group_key}:** {len(records)} record(s)")
        
        # Action buttons
        col_bulk1, col_bulk2 = st.columns(2)
        
        with col_bulk1:
            if st.button("🗑️ Proceed with Bulk Delete", type="primary", use_container_width=True):
                st.session_state.show_deletion_dialog = True
                st.session_state.deletion_mode = "bulk"
                st.rerun()
        
        with col_bulk2:
            if st.button("❌ Clear Selection", type="secondary", use_container_width=True):
                st.session_state.bulk_delete_selection = []
                st.rerun()
    else:
        st.info("Select allocations above to proceed with bulk deletion")

def show_bulk_deletion_dialog():
    """Show dialog for bulk deletion with role-based references"""
    
    st.markdown("### 🗑️ Bulk Deletion - Reference Entry")
    
    if not st.session_state.bulk_deletion_role_groups:
        st.error("No deletion groups selected")
        return
    
    # Save to undo stack
    undo_data = {
        'action': 'bulk_delete',
        'groups': st.session_state.bulk_deletion_role_groups.copy(),
        'record_counts': {k: len(v) for k, v in st.session_state.bulk_deletion_role_groups.items()}
    }
    st.session_state.undo_stack.append(undo_data)
    
    # Show reference forms for each role group
    deletion_references = {}
    
    for group_key, records in st.session_state.bulk_deletion_role_groups.items():
        st.markdown(f"---")
        st.markdown(f"#### 📋 {group_key.replace('_', ' ')} - {len(records)} record(s)")
        
        # Show sample records
        with st.expander(f"View {len(records)} record(s) in this group"):
            for record in records[:5]:  # Show first 5
                if 'IO Name' in record:
                    st.write(f"• {record.get('IO Name')} - {record.get('Venue')} - {record.get('Date')}")
                else:
                    st.write(f"• {record.get('EY Personnel')} - {record.get('Venue')} - {record.get('Date')}")
            
            if len(records) > 5:
                st.write(f"... and {len(records) - 5} more")
        
        # Reference inputs for this group
        col_ref1, col_ref2 = st.columns(2)
        
        with col_ref1:
            order_no = st.text_input(
                f"Deletion Order No. for {group_key}:",
                placeholder="e.g., SSC/Deletion/2024/001",
                key=f"bulk_order_{group_key}"
            )
        
        with col_ref2:
            reason = st.text_area(
                f"Deletion Reason for {group_key}:",
                placeholder=f"Why deleting {len(records)} {group_key.replace('_', ' ')} record(s)...",
                height=80,
                key=f"bulk_reason_{group_key}"
            )
        
        deletion_references[group_key] = {
            'order_no': order_no,
            'reason': reason,
            'count': len(records)
        }
    
    # Action buttons
    col_action1, col_action2 = st.columns(2)
    
    with col_action1:
        if st.button("✅ Confirm Bulk Deletion", type="primary", use_container_width=True):
            # Validate all references
            validation_errors = []
            for group_key, ref in deletion_references.items():
                if not ref['order_no'].strip():
                    validation_errors.append(f"❌ Order No. required for {group_key}")
                if not ref['reason'].strip():
                    validation_errors.append(f"❌ Reason required for {group_key}")
            
            if validation_errors:
                for error in validation_errors:
                    st.error(error)
                return
            
            # Perform bulk deletion
            success = perform_bulk_deletion(deletion_references)
            
            if success:
                st.session_state.show_deletion_dialog = False
                st.session_state.deletion_mode = None
                st.session_state.bulk_deletion_role_groups = {}
                st.rerun()
    
    with col_action2:
        if st.button("❌ Cancel Bulk Deletion", type="secondary", use_container_width=True):
            st.session_state.show_deletion_dialog = False
            st.session_state.deletion_mode = None
            st.session_state.bulk_deletion_role_groups = {}
            st.rerun()

def perform_bulk_deletion(deletion_references):
    """Perform bulk deletion with role-based references"""
    
    try:
        total_deleted = 0
        
        for group_key, ref in deletion_references.items():
            records = st.session_state.bulk_deletion_role_groups[group_key]
            
            for record in records:
                # Create deletion record
                deletion_record = {
                    'original_data': record,
                    'deletion_order_no': ref['order_no'].strip(),
                    'deletion_reason': ref['reason'].strip(),
                    'deletion_timestamp': datetime.now().isoformat(),
                    'exam': st.session_state.current_exam_key,
                    'record_type': 'IO' if 'IO' in group_key else 'EY',
                    'deleted_by': 'system_admin',
                    'bulk_group': group_key
                }
                
                # Add to deleted records
                st.session_state.deleted_records.append(deletion_record)
                
                # Remove from active allocations
                if 'IO' in group_key:
                    # Remove IO allocation
                    for idx, alloc in enumerate(st.session_state.allocation):
                        if (alloc.get('Sl. No.') == record.get('Sl. No.') and
                            alloc.get('IO Name') == record.get('IO Name') and
                            alloc.get('Venue') == record.get('Venue') and
                            alloc.get('Date') == record.get('Date') and
                            alloc.get('Shift') == record.get('Shift')):
                            
                            del st.session_state.allocation[idx]
                            break
                else:
                    # Remove EY allocation
                    for idx, alloc in enumerate(st.session_state.ey_allocation):
                        if (alloc.get('Sl. No.') == record.get('Sl. No.') and
                            alloc.get('EY Personnel') == record.get('EY Personnel') and
                            alloc.get('Venue') == record.get('Venue') and
                            alloc.get('Date') == record.get('Date') and
                            alloc.get('Shift') == record.get('Shift')):
                            
                            del st.session_state.ey_allocation[idx]
                            break
                
                total_deleted += 1
        
        # Renumber serial numbers
        for i, alloc in enumerate(st.session_state.allocation):
            alloc['Sl. No.'] = i + 1
        
        for i, alloc in enumerate(st.session_state.ey_allocation):
            alloc['Sl. No.'] = i + 1
        
        # Update exam data
        exam_key = st.session_state.current_exam_key
        if exam_key in st.session_state.exam_data:
            st.session_state.exam_data[exam_key]['io_allocations'] = st.session_state.allocation
            st.session_state.exam_data[exam_key]['ey_allocations'] = st.session_state.ey_allocation
        
        # Save data
        save_all_data()
        
        # Log audit event
        log_audit_event(
            event_type="bulk_deletion",
            event_data={
                "total_records": total_deleted,
                "role_groups": {k: len(v) for k, v in st.session_state.bulk_deletion_role_groups.items()},
                "references": {k: v['order_no'] for k, v in deletion_references.items()}
            },
            user_action="Bulk deletion completed"
        )
        
        st.success(f"✅ Bulk deletion completed! {total_deleted} record(s) deleted.")
        return True
        
    except Exception as e:
        st.error(f"❌ Error in bulk deletion: {str(e)}")
        return False

# ============================================================================
# DELETION SYSTEM - TIER 3: EXAM-WISE DELETION
# ============================================================================

def show_exam_deletion_dialog():
    """Show exam deletion confirmation dialog"""
    
    if not st.session_state.current_exam_key:
        st.error("No exam selected")
        return
    
    exam_key = st.session_state.current_exam_key
    
    st.markdown("### ⚠️ Exam-Wise Deletion")
    
    # Show exam info
    st.warning(f"You are about to delete the entire exam: **{exam_key}**")
    
    # Count records
    io_count = len([a for a in st.session_state.allocation 
                   if a.get('Exam') == exam_key])
    ey_count = len([a for a in st.session_state.ey_allocation 
                   if a.get('Exam') == exam_key])
    
    st.write(f"**This will delete:**")
    st.write(f"- 📊 {io_count} IO allocation(s)")
    st.write(f"- 👁️ {ey_count} EY allocation(s)")
    
    # Create backup before deletion
    backup_file = create_backup(f"PRE_DELETION_{exam_key.replace(' ', '_')}")
    
    if backup_file:
        st.success(f"✅ Backup created: `{backup_file.name}`")
        st.info("You can restore from this backup if needed.")
    else:
        st.error("❌ Failed to create backup. Deletion cannot proceed.")
        return
    
    # Deletion reference
    st.markdown("---")
    st.markdown("### 📋 Deletion Reference")
    
    deletion_order_no = st.text_input(
        "Deletion Order No.:",
        placeholder="e.g., SSC/Exam-Deletion/2024/001",
        key="exam_deletion_order"
    )
    
    deletion_reason = st.text_area(
        "Deletion Reason:",
        placeholder="Explain why this entire exam is being deleted...",
        height=100,
        key="exam_deletion_reason"
    )
    
    # Confirmation
    st.markdown("---")
    st.markdown("### ❗ Final Confirmation")
    
    confirm = st.checkbox(
        f"I understand this will permanently delete {io_count + ey_count} records from '{exam_key}'",
        value=False
    )
    
    col_confirm, col_cancel = st.columns(2)
    
    with col_confirm:
        if st.button("🗑️ DELETE ENTIRE EXAM", type="primary", use_container_width=True):
            if not confirm:
                st.error("Please confirm your understanding")
                return
            
            if not deletion_order_no.strip():
                st.error("❌ Deletion Order No. is required")
                return
            if not deletion_reason.strip():
                st.error("❌ Deletion Reason is required")
                return
            
            # Perform exam deletion
            success = delete_entire_exam(exam_key, deletion_order_no, deletion_reason, backup_file)
            
            if success:
                st.session_state.current_exam_key = ""
                st.session_state.allocation = []
                st.session_state.ey_allocation = []
                st.rerun()
    
    with col_cancel:
        if st.button("❌ Cancel", type="secondary", use_container_width=True):
            st.rerun()

def delete_entire_exam(exam_key, deletion_order_no, deletion_reason, backup_file):
    """Delete entire exam with audit trail"""
    
    try:
        # Save current exam data for undo
        exam_data = st.session_state.exam_data.get(exam_key, {})
        undo_data = {
            'action': 'delete_exam',
            'exam_key': exam_key,
            'exam_data': exam_data.copy(),
            'backup_file': backup_file.name if backup_file else None
        }
        st.session_state.undo_stack.append(undo_data)
        
        # Move all allocations to deleted records
        io_allocations = exam_data.get('io_allocations', [])
        ey_allocations = exam_data.get('ey_allocations', [])
        
        # Process IO allocations
        for record in io_allocations:
            deletion_record = {
                'original_data': record,
                'deletion_order_no': deletion_order_no.strip(),
                'deletion_reason': deletion_reason.strip(),
                'deletion_timestamp': datetime.now().isoformat(),
                'exam': exam_key,
                'record_type': 'IO',
                'deleted_by': 'system_admin',
                'deletion_type': 'exam_wise'
            }
            st.session_state.deleted_records.append(deletion_record)
        
        # Process EY allocations
        for record in ey_allocations:
            deletion_record = {
                'original_data': record,
                'deletion_order_no': deletion_order_no.strip(),
                'deletion_reason': deletion_reason.strip(),
                'deletion_timestamp': datetime.now().isoformat(),
                'exam': exam_key,
                'record_type': 'EY',
                'deleted_by': 'system_admin',
                'deletion_type': 'exam_wise'
            }
            st.session_state.deleted_records.append(deletion_record)
        
        # Remove exam from active exams
        if exam_key in st.session_state.exam_data:
            del st.session_state.exam_data[exam_key]
        
        # Remove exam references
        if exam_key in st.session_state.allocation_references:
            del st.session_state.allocation_references[exam_key]
        
        # Clear current allocations if this was the current exam
        if st.session_state.current_exam_key == exam_key:
            st.session_state.current_exam_key = ""
            st.session_state.allocation = []
            st.session_state.ey_allocation = []
        
        # Save data
        save_all_data()
        
        # Log audit event
        log_audit_event(
            event_type="exam_deletion",
            event_data={
                "exam_key": exam_key,
                "records_deleted": len(io_allocations) + len(ey_allocations),
                "io_records": len(io_allocations),
                "ey_records": len(ey_allocations),
                "deletion_order_no": deletion_order_no,
                "backup_file": backup_file.name if backup_file else "None",
                "reason": deletion_reason[:100]
            },
            user_action="Deleted entire exam"
        )
        
        st.success(f"✅ Exam '{exam_key}' deleted successfully!")
        st.info(f"Backup saved as: {backup_file.name}")
        
        return True
        
    except Exception as e:
        st.error(f"❌ Error deleting exam: {str(e)}")
        return False

# ============================================================================
# DELETED RECORDS MANAGEMENT
# ============================================================================

def show_deleted_records_manager():
    """Display deleted records management interface"""
    
    st.markdown("""
        <div style='text-align: center; padding: 20px; background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%); 
                 color: white; border-radius: 10px; margin-bottom: 30px;'>
            <h1>🗑️ DELETED RECORDS MANAGER</h1>
            <p>Complete Audit Trail & Recovery Options</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Filters and search
    st.markdown("### 🔍 Search & Filter Deleted Records")
    
    col_filter1, col_filter2, col_filter3 = st.columns(3)
    
    with col_filter1:
        filter_exam = st.selectbox(
            "Filter by Exam:",
            ["All Exams"] + sorted(set([r.get('exam', 'Unknown') for r in st.session_state.deleted_records])),
            key="deleted_filter_exam"
        )
    
    with col_filter2:
        filter_type = st.selectbox(
            "Filter by Type:",
            ["All Types", "IO", "EY"],
            key="deleted_filter_type"
        )
    
    with col_filter3:
        search_term = st.text_input(
            "Search:",
            placeholder="Search by name, venue, or order no...",
            key="deleted_search"
        )
    
    # Date range filter
    col_date1, col_date2 = st.columns(2)
    with col_date1:
        from_date = st.date_input("From Date:", value=None)
    with col_date2:
        to_date = st.date_input("To Date:", value=None)
    
    # Apply filters
    filtered_records = st.session_state.deleted_records
    
    if filter_exam != "All Exams":
        filtered_records = [r for r in filtered_records if r.get('exam') == filter_exam]
    
    if filter_type != "All Types":
        filtered_records = [r for r in filtered_records if r.get('record_type') == filter_type]
    
    if search_term:
        search_term = search_term.lower()
        filtered_records = [
            r for r in filtered_records 
            if (search_term in str(r.get('original_data', {}).get('IO Name', '')).lower() or
                search_term in str(r.get('original_data', {}).get('EY Personnel', '')).lower() or
                search_term in str(r.get('original_data', {}).get('Venue', '')).lower() or
                search_term in str(r.get('deletion_order_no', '')).lower())
        ]
    
    if from_date:
        from_datetime = datetime.combine(from_date, datetime.min.time())
        filtered_records = [
            r for r in filtered_records 
            if datetime.fromisoformat(r.get('deletion_timestamp', '2000-01-01')).date() >= from_date
        ]
    
    if to_date:
        to_datetime = datetime.combine(to_date, datetime.max.time())
        filtered_records = [
            r for r in filtered_records 
            if datetime.fromisoformat(r.get('deletion_timestamp', '2100-01-01')).date() <= to_date
        ]
    
    # Summary statistics
    st.markdown(f"### 📊 Found {len(filtered_records)} deleted record(s)")
    
    if filtered_records:
        # Group by exam for statistics
        exam_groups = {}
        for record in filtered_records:
            exam = record.get('exam', 'Unknown')
            if exam not in exam_groups:
                exam_groups[exam] = {'IO': 0, 'EY': 0}
            exam_groups[exam][record.get('record_type', 'Unknown')] += 1
        
        # Display statistics
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        
        with col_stat1:
            total_io = sum(g['IO'] for g in exam_groups.values())
            st.metric("Total IO Records", total_io)
        
        with col_stat2:
            total_ey = sum(g['EY'] for g in exam_groups.values())
            st.metric("Total EY Records", total_ey)
        
        with col_stat3:
            total_exams = len(exam_groups)
            st.metric("Total Exams", total_exams)
        
        # Selection for permanent deletion
        st.markdown("### 🗑️ Permanent Deletion Options")
        
        # Option 1: Delete selected records
        st.markdown("#### Option 1: Delete Selected Records")
        
        # Display records with checkboxes
        selected_for_permanent_deletion = []
        
        with st.expander(f"View {len(filtered_records)} Deleted Record(s)", expanded=False):
            for idx, record in enumerate(filtered_records[:50]):  # Limit to 50 for performance
                col_check, col_info = st.columns([1, 10])
                
                with col_check:
                    if st.checkbox("", key=f"perm_del_{idx}"):
                        selected_for_permanent_deletion.append(record)
                
                with col_info:
                    exam = record.get('exam', 'Unknown')
                    record_type = record.get('record_type', 'Unknown')
                    
                    if record_type == 'IO':
                        person = record.get('original_data', {}).get('IO Name', 'Unknown')
                        icon = "👨‍💼"
                    else:
                        person = record.get('original_data', {}).get('EY Personnel', 'Unknown')
                        icon = "👁️"
                    
                    venue = record.get('original_data', {}).get('Venue', 'Unknown')
                    date = record.get('original_data', {}).get('Date', 'Unknown')
                    del_date = datetime.fromisoformat(record.get('deletion_timestamp', '')).strftime("%d-%m-%Y %H:%M")
                    
                    st.write(f"{icon} **{person}** | 🏢 {venue} | 📅 {date}")
                    st.caption(f"🗑️ Deleted on {del_date} | 📋 Order: {record.get('deletion_order_no', 'N/A')}")
        
        if selected_for_permanent_deletion:
            st.warning(f"⚠️ Selected {len(selected_for_permanent_deletion)} record(s) for permanent deletion")
            
            col_del1, col_del2 = st.columns(2)
            with col_del1:
                if st.button("🔥 Delete Selected Permanently", type="primary", use_container_width=True):
                    if permanent_delete_records(selected_for_permanent_deletion):
                        st.success(f"✅ {len(selected_for_permanent_deletion)} record(s) permanently deleted")
                        st.rerun()
            
            with col_del2:
                if st.button("❌ Clear Selection", type="secondary", use_container_width=True):
                    st.rerun()
        
        # Option 2: Delete by exam
        st.markdown("#### Option 2: Delete Entire Exam Records")
        
        if exam_groups:
            selected_exam = st.selectbox(
                "Select Exam to Delete All Records:",
                ["-- Select Exam --"] + list(exam_groups.keys()),
                key="perm_del_exam"
            )
            
            if selected_exam != "-- Select Exam --":
                exam_count = exam_groups[selected_exam]['IO'] + exam_groups[selected_exam]['EY']
                st.warning(f"⚠️ This will permanently delete ALL {exam_count} record(s) from '{selected_exam}'")
                
                confirm = st.checkbox(f"I understand this action cannot be undone for '{selected_exam}'")
                
                if st.button("🔥 Delete All Exam Records", type="primary", disabled=not confirm):
                    exam_records = [r for r in filtered_records if r.get('exam') == selected_exam]
                    if permanent_delete_records(exam_records):
                        st.success(f"✅ All {len(exam_records)} record(s) from '{selected_exam}' permanently deleted")
                        st.rerun()
        
        # Option 3: Delete all records (nuclear option)
        st.markdown("#### Option 3: Delete All Records (Nuclear Option)")
        
        with st.expander("⚠️ DANGER ZONE - PERMANENT DELETE ALL"):
            st.error("This will permanently delete ALL deleted records from ALL exams. This action CANNOT be undone!")
            
            confirm1 = st.checkbox("I understand this will delete all audit trails")
            confirm2 = st.checkbox("I have exported/backed up important records")
            
            if confirm1 and confirm2:
                if st.button("☢️ DELETE ALL RECORDS PERMANENTLY", type="primary"):
                    if permanent_delete_all_records():
                        st.success("✅ All deleted records permanently removed")
                        st.rerun()
    
    else:
        st.info("No deleted records found matching your filters")

def permanent_delete_records(records_to_delete):
    """Permanently delete records from deleted records database"""
    
    try:
        # Log before deletion
        log_audit_event(
            event_type="permanent_deletion",
            event_data={
                "records_count": len(records_to_delete),
                "record_ids": [r.get('original_data', {}).get('Sl. No.', 'Unknown') for r in records_to_delete],
                "exams": list(set(r.get('exam', 'Unknown') for r in records_to_delete))
            },
            user_action="Permanently deleted records from audit trail"
        )
        
        # Remove from deleted records
        records_to_keep = []
        deleted_count = 0
        
        for record in st.session_state.deleted_records:
            if record not in records_to_delete:
                records_to_keep.append(record)
            else:
                deleted_count += 1
        
        st.session_state.deleted_records = records_to_keep
        
        # Save data
        save_all_data()
        
        return True
        
    except Exception as e:
        st.error(f"❌ Error in permanent deletion: {str(e)}")
        return False

def permanent_delete_all_records():
    """Permanently delete all records from deleted records database"""
    
    try:
        total_records = len(st.session_state.deleted_records)
        
        # Log before deletion
        log_audit_event(
            event_type="permanent_deletion_all",
            event_data={
                "total_records": total_records,
                "action": "COMPLETE_DELETION"
            },
            user_action="Permanently deleted ALL audit records"
        )
        
        # Clear all records
        st.session_state.deleted_records = []
        
        # Save data
        save_all_data()
        
        return True
        
    except Exception as e:
        st.error(f"❌ Error deleting all records: {str(e)}")
        return False

# ============================================================================
# REFERENCE MANAGEMENT SYSTEM
# ============================================================================

def show_reference_management():
    """Display reference management interface"""
    
    st.markdown("""
        <div style='text-align: center; padding: 20px; background: linear-gradient(135deg, #20b2aa 0%, #3cb371 100%); 
                 color: white; border-radius: 10px; margin-bottom: 30px;'>
            <h1>📋 REFERENCE MANAGEMENT</h1>
            <p>Order No. & Page No. System</p>
        </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["📚 View All References", "🔄 Update References", "🗑️ Delete References"])
    
    with tab1:
        show_all_references()
    
    with tab2:
        show_update_reference_interface()
    
    with tab3:
        show_reference_deletion()

def show_all_references():
    """Display all references used across exams"""
    
    if not st.session_state.allocation_references:
        st.info("No references found")
        return
    
    # Search and filter
    col_search1, col_search2 = st.columns(2)
    
    with col_search1:
        search_exam = st.text_input("Search Exam:", placeholder="Exam name contains...")
    
    with col_search2:
        search_role = st.selectbox(
            "Filter by Role:",
            ["All Roles", "Centre Coordinator", "Flying Squad", "EY Personnel"]
        )
    
    # Display references
    total_refs = 0
    for exam_key, exam_refs in st.session_state.allocation_references.items():
        if search_exam and search_exam.lower() not in exam_key.lower():
            continue
        
        exam_total = 0
        ref_rows = []
        
        for role, ref_data in exam_refs.items():
            if search_role != "All Roles" and role != search_role:
                continue
            
            exam_total += 1
            total_refs += 1
            
            ref_rows.append({
                "Exam": exam_key,
                "Role": role,
                "Order No.": ref_data.get('order_no', 'N/A'),
                "Page No.": ref_data.get('page_no', 'N/A'),
                "Created": datetime.fromisoformat(ref_data.get('timestamp', '2000-01-01')).strftime("%d-%m-%Y %H:%M"),
                "Remarks": ref_data.get('remarks', '')[:50] + "..." if len(ref_data.get('remarks', '')) > 50 else ref_data.get('remarks', '')
            })
        
        if ref_rows:
            st.markdown(f"### 📘 {exam_key}")
            ref_df = pd.DataFrame(ref_rows)
            st.dataframe(ref_df, use_container_width=True, hide_index=True)
    
    if total_refs == 0:
        st.info("No references match your search criteria")

def show_update_reference_interface():
    """Interface for updating references"""
    
    if not st.session_state.current_exam_key:
        st.warning("Please select an exam first")
        return
    
    exam_key = st.session_state.current_exam_key
    
    st.markdown(f"### 🔄 Update References for {exam_key}")
    
    # Get current allocations for this exam
    current_io = [a for a in st.session_state.allocation if a.get('Exam') == exam_key]
    current_ey = [a for a in st.session_state.ey_allocation if a.get('Exam') == exam_key]
    
    if not current_io and not current_ey:
        st.info("No allocations found for this exam")
        return
    
    # Group by role
    role_groups = {}
    
    for alloc in current_io:
        role = alloc.get('Role', 'Unknown')
        if role not in role_groups:
            role_groups[role] = []
        role_groups[role].append(alloc)
    
    for alloc in current_ey:
        role = "EY Personnel"
        if role not in role_groups:
            role_groups[role] = []
        role_groups[role].append(alloc)
    
    # Show current references
    st.markdown("#### 📋 Current References")
    
    for role, allocations in role_groups.items():
        current_ref = st.session_state.allocation_references.get(exam_key, {}).get(role, {})
        
        col_role1, col_role2 = st.columns([3, 1])
        
        with col_role1:
            st.write(f"**{role}** - {len(allocations)} allocation(s)")
            if current_ref:
                st.write(f"Current: Order No. {current_ref.get('order_no', 'N/A')}, Page {current_ref.get('page_no', 'N/A')}")
        
        with col_role2:
            if st.button(f"Update {role}", key=f"update_ref_{role}", use_container_width=True):
                st.session_state.show_update_reference = True
                st.session_state.update_reference_data = {
                    'exam_key': exam_key,
                    'role': role,
                    'allocations': allocations
                }
                st.rerun()
    
    # Update reference dialog
    if st.session_state.show_update_reference and st.session_state.update_reference_data:
        show_update_reference_dialog()

def show_update_reference_dialog():
    """Dialog for updating references"""
    
    data = st.session_state.update_reference_data
    exam_key = data['exam_key']
    role = data['role']
    allocations = data['allocations']
    
    st.markdown(f"### 📝 Update Reference for {role}")
    st.write(f"**Affects {len(allocations)} allocation(s)**")
    
    # Current reference
    current_ref = st.session_state.allocation_references.get(exam_key, {}).get(role, {})
    
    if current_ref:
        st.info(f"Current: Order No. **{current_ref.get('order_no', 'N/A')}**, Page **{current_ref.get('page_no', 'N/A')}**")
    
    # New reference inputs
    col_new1, col_new2 = st.columns(2)
    
    with col_new1:
        new_order_no = st.text_input(
            "New Order No.:",
            value=current_ref.get('order_no', ''),
            placeholder="e.g., SSC/Update/2024/001",
            key="update_order_no"
        )
    
    with col_new2:
        new_page_no = st.text_input(
            "New Page No.:",
            value=current_ref.get('page_no', ''),
            placeholder="Page number",
            key="update_page_no"
        )
    
    new_remarks = st.text_area(
        "Remarks (Optional):",
        value=current_ref.get('remarks', ''),
        placeholder="Any remarks about this update...",
        height=80,
        key="update_remarks"
    )
    
    # Update scope
    update_scope = st.radio(
        "Update Scope:",
        ["Only selected allocations", "All allocations of this role"],
        horizontal=True
    )
    
    # Action buttons
    col_action1, col_action2 = st.columns(2)
    
    with col_action1:
        if st.button("💾 Update Reference", type="primary", use_container_width=True):
            if not new_order_no.strip():
                st.error("❌ Order No. is required")
                return
            
            # Save to undo stack
            undo_data = {
                'action': 'update_reference',
                'exam_key': exam_key,
                'role': role,
                'old_reference': current_ref.copy(),
                'new_reference': {
                    'order_no': new_order_no,
                    'page_no': new_page_no,
                    'remarks': new_remarks,
                    'timestamp': datetime.now().isoformat()
                },
                'scope': update_scope,
                'affected_count': len(allocations)
            }
            st.session_state.undo_stack.append(undo_data)
            
            # Update reference in database
            if exam_key not in st.session_state.allocation_references:
                st.session_state.allocation_references[exam_key] = {}
            
            st.session_state.allocation_references[exam_key][role] = {
                'order_no': new_order_no.strip(),
                'page_no': new_page_no.strip(),
                'remarks': new_remarks.strip(),
                'timestamp': datetime.now().isoformat(),
                'updated_from': current_ref.get('order_no', '')
            }
            
            # Update allocations if scope is "all"
            if update_scope == "All allocations of this role":
                if role == "EY Personnel":
                    for alloc in st.session_state.ey_allocation:
                        if alloc.get('Exam') == exam_key:
                            alloc['Order No.'] = new_order_no.strip()
                            alloc['Page No.'] = new_page_no.strip()
                            alloc['Reference Remarks'] = new_remarks.strip()
                else:
                    for alloc in st.session_state.allocation:
                        if alloc.get('Exam') == exam_key and alloc.get('Role') == role:
                            alloc['Order No.'] = new_order_no.strip()
                            alloc['Page No.'] = new_page_no.strip()
                            alloc['Reference Remarks'] = new_remarks.strip()
            
            # Save data
            save_all_data()
            
            # Log audit event
            log_audit_event(
                event_type="reference_updated",
                event_data={
                    "exam": exam_key,
                    "role": role,
                    "old_order_no": current_ref.get('order_no', 'None'),
                    "new_order_no": new_order_no,
                    "affected_allocations": len(allocations)
                },
                user_action="Updated allocation reference"
            )
            
            st.success(f"✅ Reference updated for {role}")
            st.session_state.show_update_reference = False
            st.session_state.update_reference_data = None
            st.rerun()
    
    with col_action2:
        if st.button("❌ Cancel", type="secondary", use_container_width=True):
            st.session_state.show_update_reference = False
            st.session_state.update_reference_data = None
            st.rerun()

def show_reference_deletion():
    """Interface for deleting references"""
    
    if not st.session_state.allocation_references:
        st.info("No references to delete")
        return
    
    st.markdown("### 🗑️ Delete References")
    
    # List references for deletion
    ref_list = []
    
    for exam_key, exam_refs in st.session_state.allocation_references.items():
        for role, ref_data in exam_refs.items():
            ref_list.append({
                'exam_key': exam_key,
                'role': role,
                'order_no': ref_data.get('order_no', 'N/A'),
                'page_no': ref_data.get('page_no', 'N/A'),
                'timestamp': datetime.fromisoformat(ref_data.get('timestamp', '')).strftime("%d-%m-%Y"),
                'key': f"{exam_key}||{role}"
            })
    
    if not ref_list:
        st.info("No references found")
        return
    
    # Selection for deletion
    st.write(f"Found {len(ref_list)} reference(s)")
    
    selected_refs = []
    for ref in ref_list:
        if st.checkbox(
            f"{ref['exam_key']} - {ref['role']} (Order: {ref['order_no']})",
            key=f"del_ref_{ref['key']}"
        ):
            selected_refs.append(ref)
    
    if selected_refs:
        st.warning(f"⚠️ Selected {len(selected_refs)} reference(s) for deletion")
        
        if st.button("🗑️ Delete Selected References", type="primary"):
            # Save to undo stack
            undo_data = {
                'action': 'delete_references',
                'references': selected_refs.copy()
            }
            st.session_state.undo_stack.append(undo_data)
            
            # Delete references
            deleted_count = 0
            for ref in selected_refs:
                exam_key = ref['exam_key']
                role = ref['role']
                
                if (exam_key in st.session_state.allocation_references and 
                    role in st.session_state.allocation_references[exam_key]):
                    
                    # Log before deletion
                    log_audit_event(
                        event_type="reference_deleted",
                        event_data={
                            "exam": exam_key,
                            "role": role,
                            "order_no": ref['order_no']
                        },
                        user_action="Deleted allocation reference"
                    )
                    
                    del st.session_state.allocation_references[exam_key][role]
                    deleted_count += 1
                    
                    # Remove empty exam entries
                    if not st.session_state.allocation_references[exam_key]:
                        del st.session_state.allocation_references[exam_key]
            
            # Save data
            save_all_data()
            
            st.success(f"✅ {deleted_count} reference(s) deleted")
            st.rerun()

# ============================================================================
# UNDO/REDO SYSTEM
# ============================================================================

def perform_undo():
    """Undo last action"""
    
    if not st.session_state.undo_stack:
        st.warning("Nothing to undo")
        return
    
    last_action = st.session_state.undo_stack.pop()
    action_type = last_action.get('action', '')
    
    # Save current state to redo stack
    current_state = {
        'exam_data': st.session_state.exam_data.copy(),
        'allocation_references': st.session_state.allocation_references.copy(),
        'deleted_records': st.session_state.deleted_records.copy(),
        'allocation': st.session_state.allocation.copy(),
        'ey_allocation': st.session_state.ey_allocation.copy(),
        'current_exam_key': st.session_state.current_exam_key
    }
    st.session_state.redo_stack.append(current_state)
    
    # Handle different action types
    if action_type == 'delete_io':
        # Restore IO allocation
        record = last_action.get('record', {})
        st.session_state.allocation.append(record)
        
        # Remove from deleted records
        st.session_state.deleted_records = [
            r for r in st.session_state.deleted_records 
            if not (r.get('original_data', {}).get('Sl. No.') == record.get('Sl. No.') and
                    r.get('original_data', {}).get('IO Name') == record.get('IO Name'))
        ]
        
        st.success(f"✅ Undo: Restored {record.get('IO Name')}")
    
    elif action_type == 'delete_ey':
        # Restore EY allocation
        record = last_action.get('record', {})
        st.session_state.ey_allocation.append(record)
        
        # Remove from deleted records
        st.session_state.deleted_records = [
            r for r in st.session_state.deleted_records 
            if not (r.get('original_data', {}).get('Sl. No.') == record.get('Sl. No.') and
                    r.get('original_data', {}).get('EY Personnel') == record.get('EY Personnel'))
        ]
        
        st.success(f"✅ Undo: Restored {record.get('EY Personnel')}")
    
    elif action_type == 'bulk_delete':
        # Restore bulk deletion
        groups = last_action.get('groups', {})
        total_restored = 0
        
        for group_key, records in groups.items():
            for record in records:
                if 'IO' in group_key:
                    st.session_state.allocation.append(record)
                else:
                    st.session_state.ey_allocation.append(record)
                
                # Remove from deleted records
                st.session_state.deleted_records = [
                    r for r in st.session_state.deleted_records 
                    if not (r.get('original_data', {}).get('Sl. No.') == record.get('Sl. No.'))
                ]
                total_restored += 1
        
        st.success(f"✅ Undo: Restored {total_restored} record(s) from bulk deletion")
    
    elif action_type == 'delete_exam':
        # Restore entire exam
        exam_key = last_action.get('exam_key', '')
        exam_data = last_action.get('exam_data', {})
        
        st.session_state.exam_data[exam_key] = exam_data
        st.session_state.current_exam_key = exam_key
        st.session_state.allocation = exam_data.get('io_allocations', [])
        st.session_state.ey_allocation = exam_data.get('ey_allocations', [])
        
        # Remove exam records from deleted records
        st.session_state.deleted_records = [
            r for r in st.session_state.deleted_records 
            if r.get('exam') != exam_key
        ]
        
        st.success(f"✅ Undo: Restored exam '{exam_key}'")
    
    elif action_type == 'update_reference':
        # Restore old reference
        exam_key = last_action.get('exam_key', '')
        role = last_action.get('role', '')
        old_reference = last_action.get('old_reference', {})
        
        if exam_key not in st.session_state.allocation_references:
            st.session_state.allocation_references[exam_key] = {}
        
        st.session_state.allocation_references[exam_key][role] = old_reference
        
        st.success(f"✅ Undo: Restored reference for {role}")
    
    elif action_type == 'delete_references':
        # Restore deleted references
        references = last_action.get('references', [])
        
        for ref in references:
            exam_key = ref['exam_key']
            role = ref['role']
            
            if exam_key not in st.session_state.allocation_references:
                st.session_state.allocation_references[exam_key] = {}
            
            st.session_state.allocation_references[exam_key][role] = {
                'order_no': ref['order_no'],
                'page_no': ref['page_no'],
                'timestamp': datetime.now().isoformat(),
                'restored': True
            }
        
        st.success(f"✅ Undo: Restored {len(references)} reference(s)")
    
    # Save data
    save_all_data()
    
    # Log audit event
    log_audit_event(
        event_type="undo_action",
        event_data={
            "action_type": action_type,
            "undo_stack_size": len(st.session_state.undo_stack),
            "redo_stack_size": len(st.session_state.redo_stack)
        },
        user_action="Undo last action"
    )

def perform_redo():
    """Redo last undone action"""
    
    if not st.session_state.redo_stack:
        st.warning("Nothing to redo")
        return
    
    # Restore from redo stack
    previous_state = st.session_state.redo_stack.pop()
    
    # Save current state to undo stack
    current_state = {
        'exam_data': st.session_state.exam_data.copy(),
        'allocation_references': st.session_state.allocation_references.copy(),
        'deleted_records': st.session_state.deleted_records.copy(),
        'allocation': st.session_state.allocation.copy(),
        'ey_allocation': st.session_state.ey_allocation.copy(),
        'current_exam_key': st.session_state.current_exam_key
    }
    st.session_state.undo_stack.append(current_state)
    
    # Restore previous state
    st.session_state.exam_data = previous_state.get('exam_data', {})
    st.session_state.allocation_references = previous_state.get('allocation_references', {})
    st.session_state.deleted_records = previous_state.get('deleted_records', [])
    st.session_state.allocation = previous_state.get('allocation', [])
    st.session_state.ey_allocation = previous_state.get('ey_allocation', [])
    st.session_state.current_exam_key = previous_state.get('current_exam_key', '')
    
    # Save data
    save_all_data()
    
    # Log audit event
    log_audit_event(
        event_type="redo_action",
        event_data={
            "redo_stack_size": len(st.session_state.redo_stack),
            "undo_stack_size": len(st.session_state.undo_stack)
        },
        user_action="Redo last undone action"
    )
    
    st.success("✅ Redo: Restored previous state")

# ============================================================================
# ENHANCED DATE SELECTION SYSTEM
# ============================================================================

def create_enhanced_date_selection_grid(allocation_type="IO"):
    """
    Create enhanced date selection grid with three modes:
    1. Normal Exam Mode (IO/Flying Squad)
    2. Mock Test Mode
    3. EY Personnel Mode
    """
    
    # Initialize selection state
    if 'date_grid_state' not in st.session_state:
        st.session_state.date_grid_state = {
            'normal_dates': {},
            'mock_dates': {},
            'ey_dates': {},
            'expanded_dates': {},
            'select_all': False
        }
    
    st.session_state.date_grid_mode = allocation_type
    
    # Create main container
    st.markdown("### 📅 Date & Shift Selection")
    
    # Mode selection (only show for IO mode)
    if allocation_type == "IO":
        col_mode1, col_mode2 = st.columns([2, 1])
        with col_mode1:
            mode = st.radio(
                "Selection Mode:",
                ["Normal Exam Dates", "Mock Test Dates"],
                horizontal=True,
                key="date_selection_mode"
            )
            st.session_state.mock_test_mode = (mode == "Mock Test Dates")
        
        with col_mode2:
            if st.button("🔁 Switch to EY Mode", use_container_width=True):
                st.session_state.ey_allocation_mode = True
                st.session_state.menu = "ey"
                st.rerun()
    else:
        # EY Mode
        st.session_state.mock_test_mode = False
        mode = "Normal Exam Dates"
    
    # ============================================
    # 1. NORMAL EXAM MODE (Centre Coordinators/Flying Squad)
    # ============================================
    if not st.session_state.mock_test_mode:
        
        # Venue selection for Normal Mode
        if allocation_type == "IO":
            venues = sorted(st.session_state.venue_df['VENUE'].dropna().unique())
            if not venues:
                st.warning("No venues available. Please load venue data.")
                return []
            
            selected_venue = st.selectbox(
                "Select Venue:", 
                venues,
                key=f"venue_select_{allocation_type}",
                index=0
            )
            
            if selected_venue != st.session_state.selected_venue:
                st.session_state.selected_venue = selected_venue
                st.rerun()
            
            # Get venue data
            venue_data = st.session_state.venue_df[
                st.session_state.venue_df['VENUE'] == selected_venue
            ]
            selected_venues = [selected_venue]
        else:
            # EY Mode - multi-venue selection
            st.markdown("#### 🏢 Venue Selection")
            
            venues = sorted(st.session_state.venue_df['VENUE'].dropna().unique())
            if not venues:
                st.warning("No venues available. Please load venue data.")
                return []
            
            selected_venues = st.multiselect(
                "Select Venues (multiple allowed):",
                venues,
                default=[],
                key="ey_venue_select"
            )
            
            col_ey1, col_ey2 = st.columns(2)
            with col_ey1:
                if st.button("🎯 Select All Venues", use_container_width=True):
                    selected_venues = venues
                    st.rerun()
            
            with col_ey2:
                if st.button("🗑️ Clear All", type="secondary", use_container_width=True):
                    selected_venues = []
                    st.rerun()
            
            if not selected_venues:
                st.info("Select at least one venue to continue")
                return []
            
            # For EY mode, use first selected venue for date display
            selected_venue = selected_venues[0]
            venue_data = st.session_state.venue_df[
                st.session_state.venue_df['VENUE'] == selected_venue
            ]
        
        if venue_data.empty:
            st.warning(f"No data found for venue: {selected_venue}")
            return []
        
        # Get unique dates for selected venue
        unique_dates = sorted(venue_data['DATE'].dropna().unique())
        
        if not unique_dates:
            st.warning(f"No dates available for {selected_venue}")
            return []
        
        # Initialize date state if not exists
        venue_key = f"{st.session_state.current_exam_key}_{selected_venue}"
        if venue_key not in st.session_state.date_grid_state['normal_dates']:
            st.session_state.date_grid_state['normal_dates'][venue_key] = {}
        
        if venue_key not in st.session_state.date_grid_state['expanded_dates']:
            st.session_state.date_grid_state['expanded_dates'][venue_key] = {}
        
        # "Select All" checkbox
        all_dates_selected = True
        all_dates_partial = False
        
        # Check current selection status
        for date_str in unique_dates:
            date_key = f"{venue_key}_{date_str}"
            if date_key in st.session_state.date_grid_state['normal_dates'][venue_key]:
                date_state = st.session_state.date_grid_state['normal_dates'][venue_key][date_key]
                if not date_state.get('all_selected', False):
                    all_dates_selected = False
                    if any(date_state.get('shifts', {}).values()):
                        all_dates_partial = True
            else:
                all_dates_selected = False
        
        col_all, _ = st.columns([1, 3])
        with col_all:
            select_all = st.checkbox(
                "✓ Select All Dates/Shifts",
                value=all_dates_selected,
                key=f"select_all_{venue_key}"
            )
            
            if select_all != st.session_state.date_grid_state['select_all']:
                st.session_state.date_grid_state['select_all'] = select_all
                if select_all:
                    # Select all shifts for all dates
                    for date_str in unique_dates:
                        date_key = f"{venue_key}_{date_str}"
                        date_shifts = venue_data[venue_data['DATE'] == date_str]['SHIFT'].unique()
                        date_shifts = [str(s) for s in date_shifts if pd.notna(s) and str(s) != '']
                        
                        if date_key not in st.session_state.date_grid_state['normal_dates'][venue_key]:
                            st.session_state.date_grid_state['normal_dates'][venue_key][date_key] = {
                                'all_selected': False,
                                'shifts': {}
                            }
                        
                        for shift in date_shifts:
                            st.session_state.date_grid_state['normal_dates'][venue_key][date_key]['shifts'][shift] = True
                        st.session_state.date_grid_state['normal_dates'][venue_key][date_key]['all_selected'] = True
                else:
                    # Deselect all
                    for date_str in unique_dates:
                        date_key = f"{venue_key}_{date_str}"
                        if date_key in st.session_state.date_grid_state['normal_dates'][venue_key]:
                            for shift in st.session_state.date_grid_state['normal_dates'][venue_key][date_key]['shifts']:
                                st.session_state.date_grid_state['normal_dates'][venue_key][date_key]['shifts'][shift] = False
                            st.session_state.date_grid_state['normal_dates'][venue_key][date_key]['all_selected'] = False
                st.rerun()
        
        # Display dates in grid layout
        st.markdown(f"**Available dates for {selected_venue}:**")
        
        # Calculate number of columns based on date count
        num_dates = len(unique_dates)
        cols_per_row = 3 if num_dates > 6 else (4 if num_dates > 4 else min(4, num_dates))
        
        # Group dates into rows
        date_rows = [unique_dates[i:i + cols_per_row] for i in range(0, num_dates, cols_per_row)]
        
        for row_dates in date_rows:
            cols = st.columns(cols_per_row)
            for idx, date_str in enumerate(row_dates):
                with cols[idx]:
                    display_date_card(date_str, venue_data, venue_key, allocation_type)
        
        # Get selected date-shift combinations
        selected_date_shifts = get_selected_date_shifts(venue_key, unique_dates, venue_data, allocation_type, selected_venues)
        
        return selected_date_shifts
    
    # ============================================
    # 2. MOCK TEST MODE
    # ============================================
    else:
        st.markdown("#### 🎭 Mock Test Date Entry")
        
        col_mock1, col_mock2 = st.columns(2)
        with col_mock1:
            mock_date = st.date_input(
                "Mock Test Date:",
                value=datetime.now().date(),
                key="mock_date_input"
            )
        
        with col_mock2:
            mock_shift = st.selectbox(
                "Shift:",
                ["Morning", "Afternoon", "Evening"],
                key="mock_shift_select"
            )
        
        col_add, _ = st.columns([1, 3])
        with col_add:
            if st.button("➕ Add Mock Test Date", use_container_width=True):
                date_str = mock_date.strftime("%d-%m-%Y")
                venue_key = f"mock_{st.session_state.selected_venue}"
                
                if venue_key not in st.session_state.date_grid_state['mock_dates']:
                    st.session_state.date_grid_state['mock_dates'][venue_key] = {}
                
                date_key = f"{venue_key}_{date_str}"
                if date_key not in st.session_state.date_grid_state['mock_dates'][venue_key]:
                    st.session_state.date_grid_state['mock_dates'][venue_key][date_key] = {
                        'shifts': {},
                        'all_selected': False
                    }
                
                # Add shift
                st.session_state.date_grid_state['mock_dates'][venue_key][date_key]['shifts'][mock_shift] = True
                st.rerun()
        
        # Display mock dates
        venue_key = f"mock_{st.session_state.selected_venue}"
        if venue_key in st.session_state.date_grid_state['mock_dates']:
            mock_dates = list(st.session_state.date_grid_state['mock_dates'][venue_key].keys())
            mock_dates = [d.replace(f"{venue_key}_", "") for d in mock_dates]
            mock_dates = sorted(set(mock_dates))
            
            if mock_dates:
                st.markdown("#### Mock Test Dates Added:")
                
                # Display in grid
                cols_per_row = 3
                mock_rows = [mock_dates[i:i + cols_per_row] for i in range(0, len(mock_dates), cols_per_row)]
                
                for row_dates in mock_rows:
                    cols = st.columns(cols_per_row)
                    for idx, date_str in enumerate(row_dates):
                        with cols[idx]:
                            display_mock_date_card(date_str, venue_key)
                
                # Get selected mock date-shifts
                selected_date_shifts = get_selected_mock_date_shifts(venue_key)
                return selected_date_shifts
        
        st.info("Add mock test dates using the form above")
        return []

# ============================================================================
# ALLOCATION TABLE WITH DELETION OPTIONS
# ============================================================================

def show_allocation_table_with_controls():
    """Display allocation table with deletion options"""
    
    if not st.session_state.current_exam_key:
        st.info("No exam selected")
        return
    
    exam_key = st.session_state.current_exam_key
    
    # Header with controls
    col_header1, col_header2, col_header3, col_header4 = st.columns([2, 1, 1, 1])
    
    with col_header1:
        st.markdown(f"### 📋 Current Allocations - {exam_key}")
    
    with col_header2:
        if st.button("🗑️ Bulk Delete", use_container_width=True):
            st.session_state.show_bulk_delete = True
            st.rerun()
    
    with col_header3:
        if st.button("↩️ Undo", use_container_width=True, disabled=len(st.session_state.undo_stack) == 0):
            perform_undo()
            st.rerun()
    
    with col_header4:
        if st.button("↪️ Redo", use_container_width=True, disabled=len(st.session_state.redo_stack) == 0):
            perform_redo()
            st.rerun()
    
    # Show IO allocations
    io_allocations = [a for a in st.session_state.allocation if a.get('Exam') == exam_key]
    
    if io_allocations:
        st.markdown("#### 👨‍💼 IO Allocations")
        
        # Create DataFrame for display
        io_display_data = []
        for alloc in io_allocations:
            io_display_data.append({
                'Sl. No.': alloc.get('Sl. No.', ''),
                'IO Name': alloc.get('IO Name', ''),
                'Venue': alloc.get('Venue', ''),
                'Date': alloc.get('Date', ''),
                'Shift': alloc.get('Shift', ''),
                'Role': alloc.get('Role', ''),
                'Mock': '✓' if alloc.get('Mock Test', False) else '',
                'Order No.': alloc.get('Order No.', ''),
                'Actions': alloc.get('Sl. No.', '')  # Placeholder for actions
            })
        
        if io_display_data:
            io_df = pd.DataFrame(io_display_data)
            
            # Display table
            st.dataframe(
                io_df[['Sl. No.', 'IO Name', 'Venue', 'Date', 'Shift', 'Role', 'Mock', 'Order No.']],
                use_container_width=True,
                hide_index=True
            )
            
            # Individual deletion controls
            st.markdown("##### Individual Deletion")
            for alloc in io_allocations:
                col_del1, col_del2, col_del3, col_del4, col_del5, col_del6 = st.columns([3, 2, 2, 1, 1, 1])
                
                with col_del1:
                    st.write(f"**{alloc.get('IO Name', '')}**")
                
                with col_del2:
                    st.write(f"{alloc.get('Venue', '')}")
                
                with col_del3:
                    st.write(f"{alloc.get('Date', '')} ({alloc.get('Shift', '')})")
                
                with col_del4:
                    st.write(f"{alloc.get('Role', '')}")
                
                with col_del5:
                    if st.button("🗑️", key=f"del_io_{alloc.get('Sl. No.', '')}", help="Delete this entry"):
                        st.session_state.deletion_mode = "single"
                        st.session_state.selected_deletions = [alloc]
                        st.session_state.show_deletion_dialog = True
                        st.rerun()
                
                with col_del6:
                    if st.button("📝", key=f"edit_io_{alloc.get('Sl. No.', '')}", help="Edit this entry"):
                        st.warning("Edit functionality coming soon")
    
    # Show EY allocations
    ey_allocations = [a for a in st.session_state.ey_allocation if a.get('Exam') == exam_key]
    
    if ey_allocations:
        st.markdown("---")
        st.markdown("#### 👁️ EY Allocations")
        
        # Create DataFrame for display
        ey_display_data = []
        for alloc in ey_allocations:
            ey_display_data.append({
                'Sl. No.': alloc.get('Sl. No.', ''),
                'EY Personnel': alloc.get('EY Personnel', ''),
                'Venue': alloc.get('Venue', ''),
                'Date': alloc.get('Date', ''),
                'Shift': alloc.get('Shift', ''),
                'Rate (₹)': alloc.get('Rate (₹)', ''),
                'Order No.': alloc.get('Order No.', ''),
                'Actions': alloc.get('Sl. No.', '')
            })
        
        if ey_display_data:
            ey_df = pd.DataFrame(ey_display_data)
            
            # Display table
            st.dataframe(
                ey_df[['Sl. No.', 'EY Personnel', 'Venue', 'Date', 'Shift', 'Rate (₹)', 'Order No.']],
                use_container_width=True,
                hide_index=True
            )
            
            # Individual deletion controls
            st.markdown("##### Individual Deletion")
            for alloc in ey_allocations:
                col_del1, col_del2, col_del3, col_del4, col_del5 = st.columns([3, 2, 2, 1, 1])
                
                with col_del1:
                    st.write(f"**{alloc.get('EY Personnel', '')}**")
                
                with col_del2:
                    st.write(f"{alloc.get('Venue', '')}")
                
                with col_del3:
                    st.write(f"{alloc.get('Date', '')} ({alloc.get('Shift', '')})")
                
                with col_del4:
                    st.write(f"₹{alloc.get('Rate (₹)', '')}")
                
                with col_del5:
                    if st.button("🗑️", key=f"del_ey_{alloc.get('Sl. No.', '')}", help="Delete this entry"):
                        st.session_state.deletion_mode = "single"
                        st.session_state.selected_deletions = [alloc]
                        st.session_state.show_deletion_dialog = True
                        st.rerun()
    
    # Delete Last Entry button
    if io_allocations or ey_allocations:
        st.markdown("---")
        col_last1, col_last2 = st.columns([3, 1])
        
        with col_last1:
            st.info("Quick Actions:")
        
        with col_last2:
            if st.button("🗑️ Delete Last Entry", type="secondary", use_container_width=True):
                # Find most recent entry
                recent_io = io_allocations[-1] if io_allocations else None
                recent_ey = ey_allocations[-1] if ey_allocations else None
                
                if recent_io and recent_ey:
                    # Compare timestamps
                    io_time = datetime.fromisoformat(recent_io.get('Timestamp', '2000-01-01'))
                    ey_time = datetime.fromisoformat(recent_ey.get('Timestamp', '2000-01-01'))
                    
                    if io_time > ey_time:
                        recent = recent_io
                        record_type = "IO"
                    else:
                        recent = recent_ey
                        record_type = "EY"
                elif recent_io:
                    recent = recent_io
                    record_type = "IO"
                elif recent_ey:
                    recent = recent_ey
                    record_type = "EY"
                else:
                    st.warning("No entries to delete")
                    return
                
                st.session_state.deletion_mode = "single"
                st.session_state.selected_deletions = [recent]
                st.session_state.show_deletion_dialog = True
                st.rerun()
    
    # Show empty message if no allocations
    if not io_allocations and not ey_allocations:
        st.info("No allocations found for this exam")

# ============================================================================
# MAIN MODULES WITH INTEGRATED DELETION
# ============================================================================

def show_dashboard():
    """Display main dashboard"""
    st.markdown("""
        <div style='text-align: center; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                 color: white; border-radius: 10px; margin-bottom: 30px;'>
            <h1>📊 SYSTEM DASHBOARD</h1>
            <p>Enhanced Deletion & Record Management System</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Quick Stats
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        active_io = len([a for a in st.session_state.allocation 
                        if a.get('Exam') == st.session_state.current_exam_key])
        st.metric("👨‍💼 Active IO Allocations", active_io)
    
    with col2:
        active_ey = len([a for a in st.session_state.ey_allocation 
                        if a.get('Exam') == st.session_state.current_exam_key])
        st.metric("👁️ Active EY Allocations", active_ey)
    
    with col3:
        st.metric("🗑️ Deleted Records", len(st.session_state.deleted_records))
    
    with col4:
        undo_count = len(st.session_state.undo_stack)
        redo_count = len(st.session_state.redo_stack)
        st.metric("↩️ Undo/Redo Stack", f"{undo_count}/{redo_count}")
    
    # System Features
    st.markdown("### 🚀 Enhanced Deletion System")
    
    col_feat1, col_feat2, col_feat3 = st.columns(3)
    
    with col_feat1:
        st.markdown("""
            <div style='padding: 15px; background: #f8f9fa; border-radius: 8px;'>
                <h4>🗑️ Three-Tier Deletion</h4>
                <p>• Single entry deletion</p>
                <p>• Bulk deletion by role</p>
                <p>• Exam-wise deletion</p>
            </div>
        """, unsafe_allow_html=True)
    
    with col_feat2:
        st.markdown("""
            <div style='padding: 15px; background: #f8f9fa; border-radius: 8px;'>
                <h4>📋 Audit Trail</h4>
                <p>• Complete deletion history</p>
                <p>• Mandatory references</p>
                <p>• Searchable records</p>
            </div>
        """, unsafe_allow_html=True)
    
    with col_feat3:
        st.markdown("""
            <div style='padding: 15px; background: #f8f9fa; border-radius: 8px;'>
                <h4>🔄 Recovery Options</h4>
                <p>• Undo/Redo functionality</p>
                <p>• Permanent deletion control</p>
                <p>• Backup before major deletions</p>
            </div>
        """, unsafe_allow_html=True)
    
    # Quick Actions
    st.markdown("### ⚡ Quick Actions")
    
    col_act1, col_act2, col_act3, col_act4 = st.columns(4)
    
    with col_act1:
        if st.button("🗑️ View Deleted Records", use_container_width=True):
            st.session_state.menu = "deleted_records"
            st.rerun()
    
    with col_act2:
        if st.button("📋 Manage References", use_container_width=True):
            st.session_state.menu = "references"
            st.rerun()
    
    with col_act3:
        if st.button("↩️ Undo Last Action", use_container_width=True, disabled=len(st.session_state.undo_stack) == 0):
            perform_undo()
            st.rerun()
    
    with col_act4:
        if st.button("📊 View All Reports", use_container_width=True):
            st.session_state.menu = "reports"
            st.rerun()

def show_exam_management():
    """Display exam management interface"""
    st.markdown("""
        <div style='text-align: center; padding: 20px; background: linear-gradient(135deg, #20b2aa 0%, #3cb371 100%); 
                 color: white; border-radius: 10px; margin-bottom: 30px;'>
            <h1>📝 EXAM MANAGEMENT</h1>
            <p>With Exam-Wise Deletion</p>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 🆕 Create / Update Exam")
        
        exam_name = st.text_input("Exam Name:", placeholder="e.g., Combined Graduate Level Examination")
        
        current_year = datetime.now().year
        year_options = [str(y) for y in range(current_year - 5, current_year + 3)]
        exam_year = st.selectbox("Exam Year:", year_options, index=0)
        
        col_create1, col_create2 = st.columns(2)
        
        with col_create1:
            if st.button("✅ Create/Update Exam", use_container_width=True):
                if exam_name.strip():
                    exam_key = f"{exam_name.strip()} - {exam_year}"
                    
                    st.session_state.current_exam_key = exam_key
                    st.session_state.exam_name = exam_name.strip()
                    st.session_state.exam_year = exam_year
                    
                    if exam_key not in st.session_state.exam_data:
                        st.session_state.exam_data[exam_key] = {
                            'io_allocations': [],
                            'ey_allocations': []
                        }
                        st.success(f"🎉 New exam '{exam_key}' created!")
                    else:
                        exam_data = st.session_state.exam_data[exam_key]
                        if isinstance(exam_data, dict):
                            st.session_state.allocation = exam_data.get('io_allocations', [])
                            st.session_state.ey_allocation = exam_data.get('ey_allocations', [])
                        else:
                            st.session_state.allocation = exam_data
                            st.session_state.ey_allocation = []
                        
                        st.success(f"📂 Exam '{exam_key}' loaded!")
                    
                    save_all_data()
                    st.rerun()
                else:
                    st.error("Please enter an exam name")
    
    with col2:
        st.markdown("### 📂 Select Existing Exam")
        
        exams = sorted(st.session_state.exam_data.keys())
        if exams:
            selected_exam = st.selectbox("Choose Exam:", exams, index=0)
            
            col_load1, col_load2 = st.columns(2)
            
            with col_load1:
                if st.button("📥 Load Exam", use_container_width=True):
                    st.session_state.current_exam_key = selected_exam
                    
                    exam_data = st.session_state.exam_data[selected_exam]
                    if isinstance(exam_data, dict):
                        st.session_state.allocation = exam_data.get('io_allocations', [])
                        st.session_state.ey_allocation = exam_data.get('ey_allocations', [])
                    else:
                        st.session_state.allocation = exam_data
                        st.session_state.ey_allocation = []
                    
                    if " - " in selected_exam:
                        name, year = selected_exam.split(" - ", 1)
                        st.session_state.exam_name = name
                        st.session_state.exam_year = year
                    
                    st.success(f"✅ Exam loaded successfully!")
                    st.rerun()
            
            with col_load2:
                if st.button("🗑️ Delete Exam", type="secondary", use_container_width=True):
                    st.session_state.deletion_mode = "exam"
                    st.rerun()
        else:
            st.info("No exams available")
    
    # Exam deletion dialog
    if st.session_state.deletion_mode == "exam":
        show_exam_deletion_dialog()
    
    # Current allocations display
    if st.session_state.current_exam_key:
        show_allocation_table_with_controls()

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    """Main application entry point"""
    try:
        # Configure page
        st.set_page_config(
            page_title="SSC (ER) Kolkata - Enhanced Deletion System",
            page_icon="🏛️",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # Apply custom CSS
        st.markdown("""
            <style>
            .main-header {
                text-align: center;
                padding: 1.5rem 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border-radius: 10px;
                margin-bottom: 2rem;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            }
            
            .card {
                background: white;
                padding: 1.5rem;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                margin-bottom: 1rem;
            }
            
            .stButton > button {
                border-radius: 8px;
                font-weight: 500;
            }
            
            .stTabs [data-baseweb="tab-list"] {
                gap: 8px;
            }
            
            .stTabs [data-baseweb="tab"] {
                height: 50px;
                background-color: #f8f9fa;
                border-radius: 8px 8px 0 0;
                font-weight: 500;
            }
            
            .stTabs [aria-selected="true"] {
                background-color: #4169e1;
                color: white;
            }
            
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            
            /* Deletion warning colors */
            .deletion-warning {
                background-color: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 8px;
                padding: 10px;
                margin: 10px 0;
            }
            
            .audit-record {
                background-color: #f8f9fa;
                border-left: 4px solid #6c757d;
                padding: 10px;
                margin: 5px 0;
                border-radius: 4px;
            }
            </style>
        """, unsafe_allow_html=True)
        
        # Initialize session state
        initialize_session_state()
        
        # Load existing data
        load_all_data()
        
        # Sidebar navigation
        with st.sidebar:
            st.markdown("""
                <div style='text-align: center; padding: 20px 0;'>
                    <h2>📋 Navigation</h2>
                    <p style='font-size: 0.9rem; color: #bdc3c7;'>Enhanced Deletion System</p>
                </div>
            """, unsafe_allow_html=True)
            
            # Menu selection
            menu_options = {
                "🏠 Dashboard": "dashboard",
                "📝 Exam Management": "exam",
                "👨‍💼 Centre Coordinator": "io",
                "👁️ EY Personnel": "ey",
                "📊 Reports": "reports",
                "🗑️ Deleted Records": "deleted_records",
                "📋 References": "references",
                "⚙️ Settings": "settings"
            }
            
            selected_menu = st.radio(
                "Select Module:",
                list(menu_options.keys()),
                label_visibility="collapsed"
            )
            
            # Update session state
            st.session_state.menu = menu_options[selected_menu]
            
            st.markdown("---")
            
            # Current exam info
            st.markdown("### 🎯 Current Exam")
            if st.session_state.current_exam_key:
                st.success(f"**{st.session_state.current_exam_key[:30]}{'...' if len(st.session_state.current_exam_key) > 30 else ''}**")
                
                current_io = len([a for a in st.session_state.allocation 
                                if a.get('Exam') == st.session_state.current_exam_key])
                current_ey = len([a for a in st.session_state.ey_allocation 
                                if a.get('Exam') == st.session_state.current_exam_key])
                
                col_stat1, col_stat2 = st.columns(2)
                with col_stat1:
                    st.metric("IO", current_io)
                with col_stat2:
                    st.metric("EY", current_ey)
            else:
                st.warning("No exam selected")
            
            st.markdown("---")
            
            # Quick actions with undo/redo
            st.markdown("### ⚡ Quick Actions")
            
            col_q1, col_q2, col_q3 = st.columns(3)
            
            with col_q1:
                if st.button("💾 Save", use_container_width=True):
                    save_all_data()
                    st.success("Data saved!")
            
            with col_q2:
                undo_disabled = len(st.session_state.undo_stack) == 0
                if st.button("↩️ Undo", use_container_width=True, disabled=undo_disabled):
                    perform_undo()
                    st.rerun()
            
            with col_q3:
                redo_disabled = len(st.session_state.redo_stack) == 0
                if st.button("↪️ Redo", use_container_width=True, disabled=redo_disabled):
                    perform_redo()
                    st.rerun()
            
            if st.button("📥 Load Defaults", use_container_width=True):
                load_default_master_data()
                st.rerun()
        
        # Main content area
        try:
            # Handle deletion dialogs first
            if st.session_state.show_deletion_dialog:
                if st.session_state.deletion_mode == "single" and st.session_state.selected_deletions:
                    record = st.session_state.selected_deletions[0]
                    record_type = "IO" if 'IO Name' in record else "EY"
                    show_deletion_dialog(record, record_type)
                elif st.session_state.deletion_mode == "bulk":
                    show_bulk_deletion_dialog()
            
            # Handle bulk delete interface
            if st.session_state.show_bulk_delete:
                show_bulk_delete_interface()
                if st.button("← Back to Allocations", use_container_width=True):
                    st.session_state.show_bulk_delete = False
                    st.rerun()
                return
            
            # Display selected module
            if st.session_state.menu == "dashboard":
                show_dashboard()
            elif st.session_state.menu == "exam":
                show_exam_management()
            elif st.session_state.menu == "io":
                # Show existing centre coordinator module (not included in this code for brevity)
                st.info("Centre Coordinator module with enhanced date selection")
                # show_centre_coordinator() would go here
            elif st.session_state.menu == "ey":
                # Show existing EY module (not included in this code for brevity)
                st.info("EY Personnel module with enhanced date selection")
                # show_ey_personnel() would go here
            elif st.session_state.menu == "reports":
                # Show existing reports module (not included in this code for brevity)
                st.info("Reports module")
                # show_reports() would go here
            elif st.session_state.menu == "deleted_records":
                show_deleted_records_manager()
            elif st.session_state.menu == "references":
                show_reference_management()
            elif st.session_state.menu == "settings":
                # Show existing settings module (not included in this code for brevity)
                st.info("Settings module")
                # show_settings() would go here
            else:
                show_dashboard()
                
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.code(traceback.format_exc())
    
    except Exception as e:
        st.error(f"Critical error: {str(e)}")

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    main()
