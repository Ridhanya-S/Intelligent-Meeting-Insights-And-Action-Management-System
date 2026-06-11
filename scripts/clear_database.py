#!/usr/bin/env python3
"""
Script to clear all data from the database.
This will delete all rows from all tables but keep the table structure intact.
"""
import sys
from pathlib import Path

# Add backend directory to Python path
_backend_root = Path(__file__).parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from backend.meeting_summarizer.config import Config
import sqlite3


def clear_database():
    """Clear all data from the database"""
    db_path = Config.DATABASE_PATH
    
    if not db_path.exists():
        print(f"❌ Database not found at: {db_path}")
        print("💡 The database will be created automatically when you run the application.")
        return
    
    print(f"🗄️  Database: {db_path}")
    print(f"📏 Size before: {db_path.stat().st_size / 1024:.2f} KB")
    
    # Confirm deletion
    response = input("\n⚠️  WARNING: This will delete ALL data from the database!\n"
                    "   This includes:\n"
                    "   - All meetings\n"
                    "   - All action items\n"
                    "   - All processed files records\n"
                    "   - All email mappings\n\n"
                    "   Type 'DELETE' to confirm: ")
    
    if response != 'DELETE':
        print("❌ Operation cancelled.")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = [row[0] for row in cursor.fetchall()]
        
        if not tables:
            print("\n⚠️  No tables found in database.")
            conn.close()
            return
        
        print(f"\n📚 Found {len(tables)} table(s): {', '.join(tables)}")
        
        # Get row counts before deletion
        print("\n📊 Row counts before deletion:")
        for table_name in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  {table_name:<30} {count:>10} rows")
        
        # Delete all data from each table
        print("\n🗑️  Deleting data...")
        deleted_counts = {}
        
        for table_name in tables:
            cursor.execute(f"DELETE FROM {table_name}")
            deleted_counts[table_name] = cursor.rowcount
            print(f"  ✓ Deleted {cursor.rowcount} rows from {table_name}")
        
        # Commit changes
        conn.commit()
        
        # Verify deletion
        print("\n✅ Verification:")
        for table_name in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            if count == 0:
                print(f"  ✓ {table_name}: {count} rows (cleared)")
            else:
                print(f"  ⚠️  {table_name}: {count} rows remaining")
        
        # Vacuum database to reclaim space
        print("\n🧹 Vacuuming database to reclaim space...")
        cursor.execute("VACUUM")
        conn.commit()
        
        print(f"\n📏 Size after: {db_path.stat().st_size / 1024:.2f} KB")
        
        conn.close()
        
        print("\n✅ Database cleared successfully!")
        print("💡 Table structures are preserved. The database is ready for new data.")
        
    except sqlite3.Error as e:
        print(f"\n❌ Error clearing database: {e}")
        if conn:
            conn.rollback()
            conn.close()


if __name__ == "__main__":
    clear_database()

