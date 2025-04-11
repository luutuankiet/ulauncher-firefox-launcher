import sqlite3
import tempfile
import shutil
import configparser
import os
import logging
import urllib.parse

logger = logging.getLogger(__name__)


class FirefoxDatabase:

    def __init__(self):
        #   Results order
        self.order = None

        #   Results number
        self.limit = None

        #   Set database location
        db_location = self.searchPlaces()

        #   Temporary  file
        #   Using FF63 the DB was locked for exclusive use of FF
        #   TODO:   Regular updates of the temporary file
        temporary_db_location = tempfile.mktemp()
        shutil.copyfile(db_location, temporary_db_location)

        #   Open Firefox database
        self.conn = sqlite3.connect(temporary_db_location)

        #   External functions
        self.conn.create_function("hostname", 1, self.__getHostname)

    def searchPlaces(self):
        """Find the Firefox places.sqlite database file by looking for .default profiles"""
        # Get the user's home directory
        home = os.environ.get("HOME")
        
        # List of possible Firefox profile base paths
        possible_base_paths = [
            os.path.join(home, ".mozilla/firefox/"),
            os.path.join(home, "snap/firefox/common/.mozilla/firefox/"),
            os.path.join(home, "snap/firefox/current/.mozilla/firefox/"),
            os.path.join(home, ".local/share/firefox/"),
            os.path.join(home, ".local/share/firefoxpwa/profiles/")
        ]
        
        # Search each base path for directories containing ".default"
        for base_path in possible_base_paths:
            if not os.path.exists(base_path):
                continue
                
            try:
                # List all items in the directory
                for item in os.listdir(base_path):
                    # Check if this is a directory and has ".default" in its name
                    item_path = os.path.join(base_path, item)
                    if os.path.isdir(item_path) and ".default" in item:
                        # Check if places.sqlite exists in this profile
                        places_path = os.path.join(item_path, "places.sqlite")
                        if os.path.exists(places_path):
                            logger.debug(f"Found .default profile with places.sqlite: {places_path}")
                            return places_path
            except Exception as e:
                logger.debug(f"Error searching directory {base_path}: {str(e)}")
        
        # If we couldn't find any .default profile with places.sqlite
        logger.error("No Firefox .default profile with places.sqlite found")
        return None

    #   Get hostname from url
    def __getHostname(self, string):
        return urllib.parse.urlsplit(string).netloc

    def search(self, query_str):

        #   Search subquery
        terms = query_str.split(" ")
        term_where = []
        for term in terms:
            term_where.append(
                f'((url LIKE "%{term}%") OR (moz_bookmarks.title LIKE "%{term}%") OR (moz_places.title LIKE "%{term}%"))'
            )

        where = " AND ".join(term_where)

        #    Order subquery
        order_by_dict = {
            "frequency": "frequency",
            "visit": "visit_count",
            "recent": "last_visit_date",
        }
        order_by = order_by_dict.get(self.order, "url")

        query = f"""SELECT 
            url, 
            CASE WHEN moz_bookmarks.title <> '' 
                THEN moz_bookmarks.title
                ELSE moz_places.title 
            END AS label,
            CASE WHEN moz_bookmarks.title <> '' 
                THEN 1
                ELSE 0 
            END AS is_bookmark
            FROM moz_places
                LEFT OUTER JOIN moz_bookmarks ON(moz_bookmarks.fk = moz_places.id)
            WHERE {where}
            ORDER BY is_bookmark DESC, {order_by} DESC
            LIMIT {self.limit};"""

        #   Query execution
        rows = []
        try:
            cursor = self.conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
        except Exception as e:
            logger.error("Error in query (%s) execution: %s" % (query, e))
        return rows

    def close(self):
        self.conn.close()
