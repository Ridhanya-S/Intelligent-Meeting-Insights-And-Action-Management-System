#!/usr/bin/env python3
"""
Database Visualization Script

View SQLite database tables and data in a readable format.
"""
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

# Add backend to path
_backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(_backend_root))

from backend.meeting_summarizer.config import Config


def print_table_info(cursor, table_name):
    """Print table structure and sample data"""
    print(f"\n{'='*80}")
    print(f"📋 TABLE: {table_name}")
    print(f"{'='*80}")
    
    # Get table schema
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    
    print("\n📊 Schema:")
    print(f"{'Column Name':<25} {'Type':<15} {'Nullable':<10} {'Primary Key'}")
    print("-" * 80)
    for col in columns:
        cid, name, col_type, notnull, default, pk = col
        nullable = "NO" if notnull else "YES"
        primary = "YES" if pk else "NO"
        print(f"{name:<25} {col_type:<15} {nullable:<10} {primary}")
    
    # Get row count
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    print(f"\n📈 Total Rows: {count}")
    
    # Show sample data (first 5 rows)
    if count > 0:
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
        rows = cursor.fetchall()
        col_names = [col[1] for col in columns]
        
        print(f"\n📝 Sample Data (showing first {min(5, count)} rows):")
        print("-" * 80)
        
        # Print header
        header = " | ".join([f"{name[:15]:<15}" for name in col_names])
        print(header)
        print("-" * 80)
        
        # Print rows
        for row in rows:
            row_str = " | ".join([f"{str(val)[:15]:<15}" if val else "None".ljust(15) for val in row])
            print(row_str)


def main():
    """Main function to display database information"""
    db_path = Config.DATABASE_PATH
    
    if not db_path.exists():
        print(f"❌ Database not found at: {db_path}")
        print("💡 The database will be created automatically when you run the application.")
        return
    
    print(f"🗄️  Database: SQLite")
    print(f"📍 Location: {db_path}")
    print(f"📏 Size: {db_path.stat().st_size / 1024:.2f} KB")
    
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
        
        # Display each table
        for table_name in tables:
            print_table_info(cursor, table_name)
        
        # Summary
        print(f"\n{'='*80}")
        print("📊 DATABASE SUMMARY")
        print(f"{'='*80}")
        for table_name in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  {table_name:<30} {count:>10} rows")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ Error reading database: {e}")


if __name__ == "__main__":
    main()

