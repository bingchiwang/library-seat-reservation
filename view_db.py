import sqlite3

def show_db():
    conn = sqlite3.connect('library_seats.db')
    cursor = conn.cursor()
    
    tables = ['users', 'seats', 'bookings']
    
    for table in tables:
        print(f"=== {table.upper()} ===")
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in cursor.fetchall()]
            
            # Hide hashed_password for users
            if table == 'users' and 'hashed_password' in columns:
                columns.remove('hashed_password')
            
            if not columns:
                print("Table is empty or not created yet.\n")
                continue
                
            cols_str = ", ".join(columns)
            cursor.execute(f"SELECT {cols_str} FROM {table}")
            rows = cursor.fetchall()
            
            print(" | ".join(columns))
            print("-" * 40)
            for row in rows:
                print(" | ".join(str(val) for val in row))
            print("\n")
        except Exception as e:
            print(f"無法讀取 {table}: {e}\n")

    conn.close()

if __name__ == "__main__":
    show_db()
