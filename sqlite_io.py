import sqlite3

nome_db = 'Schede_US.db'
nome_tabella = 'Scheda_US'

def load_sqlite_db(nome_db,nome_tabella):

    conn = sqlite3.connect(nome_db)
    #conn = sqlite3.connect('test_sqlite.db')

    tabella = conn.cursor()

    for row in tabella.execute('SELECT * FROM '+nome_tabella):
            print("l'unità "+row[0]+ " ha descrizione: "+row[1])

    conn.close()

    return tabella
