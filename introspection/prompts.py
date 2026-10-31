
ALLOWED_TABLES = {
    "album",
    "artist",
    "employee",
    "customer",
    "genre",
    "invoice",
    "invoice_line",
    "media_type",
    "playlist",
    "playlist_track",
    "track",
}

SCHEMA_TEXT_PROMPT = """
Table: album
- album_id: integer, primary key, not null
- title: varchar(160), not null
- artist_id: integer, not null

Table: artist
- artist_id: integer, primary key, not null
- name: varchar(120), nullable

Table: customer
- customer_id: integer, primary key, not null
- first_name: varchar(40), not null
- last_name: varchar(20), not null
- company: varchar(80), nullable
- address: varchar(70), nullable
- city: varchar(40), nullable
- state: varchar(40), nullable
- country: varchar(40), nullable
- postal_code: varchar(10), nullable
- phone: varchar(24), nullable
- fax: varchar(24), nullable
- email: varchar(60), not null
- support_rep_id: integer, nullable

Table: employee
- employee_id: integer, primary key, not null
- last_name: varchar(20), not null
- first_name: varchar(20), not null
- title: varchar(30), nullable
- reports_to: integer, nullable
- birth_date: timestamp, nullable
- hire_date: timestamp, nullable
- address: varchar(70), nullable
- city: varchar(40), nullable
- state: varchar(40), nullable
- country: varchar(40), nullable
- postal_code: varchar(10), nullable
- phone: varchar(24), nullable
- fax: varchar(24), nullable
- email: varchar(60), nullable

Table: genre
- genre_id: integer, primary key, not null
- name: varchar(120), nullable

Table: invoice
- invoice_id: integer, primary key, not null
- customer_id: integer, not null
- invoice_date: timestamp, not null
- billing_address: varchar(70), nullable
- billing_city: varchar(40), nullable
- billing_state: varchar(40), nullable
- billing_country: varchar(40), nullable
- billing_postal_code: varchar(10), nullable
- total: numeric(10,2), not null

Table: invoice_line
- invoice_line_id: integer, primary key, not null
- invoice_id: integer, not null
- track_id: integer, not null
- unit_price: numeric(10,2), not null
- quantity: integer, not null

Table: media_type
- media_type_id: integer, primary key, not null
- name: varchar(120), nullable

Table: playlist
- playlist_id: integer, primary key, not null
- name: varchar(120), nullable

Table: playlist_track
- playlist_id: integer, primary key, not null
- track_id: integer, primary key, not null

Table: track
- track_id: integer, primary key, not null
- name: varchar(200), not null
- album_id: integer, nullable
- media_type_id: integer, not null
- genre_id: integer, nullable
- composer: varchar(220), nullable
- milliseconds: integer, not null
- bytes: integer, nullable
- unit_price: numeric(10,2), not null
"""

relationships = """
album.artist_id -> artist.artist_id
customer.support_rep_id -> employee.employee_id
employee.reports_to -> employee.employee_id
invoice.customer_id -> customer.customer_id
invoice_line.invoice_id -> invoice.invoice_id
invoice_line.track_id -> track.track_id
playlist_track.playlist_id -> playlist.playlist_id
playlist_track.track_id -> track.track_id
track.album_id -> album.album_id
track.media_type_id -> media_type.media_type_id
track.genre_id -> genre.genre_id
"""
FEW_SHOT_EXAMPLES = [
    {
        "question": "How many customers are there?",
        "sql": "SELECT COUNT(*) AS customer_count FROM customer;",
    },
    {
        "question": "Top 5 countries by total sales",
        "sql": """
            SELECT billing_country, SUM(total) AS sales
            FROM invoice
            GROUP BY billing_country
            ORDER BY sales DESC
            LIMIT 5;
        """.strip(),
    },
    {
        "question": "Which 5 artists have the most tracks?",
        "sql": """
            SELECT artist.name AS artist_name,
                   COUNT(track.track_id) AS track_count
            FROM artist
            JOIN album ON album.artist_id = artist.artist_id
            JOIN track ON track.album_id = album.album_id
            GROUP BY artist.artist_id, artist.name
            ORDER BY track_count DESC
            LIMIT 5;
        """.strip(),
    },
]


few_shot_text = "\n\n".join(
    f"Question: {example['question']}\n{example['sql'].removeprefix('SQL:').strip()}"
    for example in FEW_SHOT_EXAMPLES
)


SQL_SYSTEM_PROMPT = f"""You generate PostgreSQL queries for a read-only data assistant.

Return exactly one of these:
1. For an answerable read-only question, one SELECT query and nothing else.
2. If the user asks to change data, including deleting, updating, or inserting rows,
   return exactly: WRITE_REQUEST
3. If the question cannot be answered from the schema, return exactly: UNANSWERABLE

Rules:
- Use only the tables and columns listed in the schema.
- Names use lowercase snake_case. Use them exactly as shown.
- Use only the listed relationships when joining tables.
- Do not invent tables, columns, or relationships.
- Do not include Markdown fences or labels such as "SQL:".

Examples:
{few_shot_text}

Schema:
{SCHEMA_TEXT_PROMPT}
"""



SUMMARY_SYSTEM_PROMPT = """You are a data analyst.
Write 2-3 sentences summarizing the query result below.
Only state facts that appear in the data. Do not guess or add outside knowledge.
"""