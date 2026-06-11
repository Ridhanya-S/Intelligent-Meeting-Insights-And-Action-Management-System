"""
Reminder Sender Script
Sends reminders to action item owners 24 hours before deadlines
Can be run as a cron job or scheduled task (if auto-send is disabled)
"""
import sys
from pathlib import Path

# Add backend directory to Python path
_backend_root = Path(__file__).parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from backend.meeting_summarizer.integrations.action_item_manager import ActionItemManager


def main():
    """Send all pending reminders"""
    print("=" * 60)
    print("Sending Action Item Reminders")
    print("=" * 60)
    
    manager = ActionItemManager()
    
    # Get pending reminders
    pending_items = manager.get_pending_reminders()
    
    if not pending_items:
        print("No reminders to send.")
        return 0
    
    print(f"Found {len(pending_items)} action items needing reminders\n")
    
    # Send reminders
    results = manager.send_all_pending_reminders()
    
    print("\n" + "=" * 60)
    print("Reminder Summary")
    print("=" * 60)
    print(f"Total items: {results['total']}")
    print(f"Reminders sent: {results['sent']}")
    print(f"Failed: {results['failed']}")
    print("=" * 60)
    
    return 0 if results['failed'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

