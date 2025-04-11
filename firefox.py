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
        # List of possible Firefox paths to check
        possible_paths = [
            os.path.join(os.environ["HOME"], ".mozilla/firefox/"),
            os.path.join(os.environ["HOME"], "snap/firefox/common/.mozilla/firefox/"),
            # Add more potential snap paths
            os.path.join(os.environ["HOME"], "snap/firefox/current/.mozilla/firefox/"),
            "/var/lib/snapd/snap/firefox/common/.mozilla/firefox/",
            # For Lubuntu-specific snap path (if different)
            os.path.join(os.environ["HOME"], ".var/app/org.mozilla.firefox/.mozilla/firefox/")
        ]
        
        firefox_path = None
        
        # Try each path until we find one that exists
        for path in possible_paths:
            if os.path.exists(path):
                firefox_path = path
                logger.debug(f"Found Firefox path: {firefox_path}")
                break
        
        if not firefox_path:
            logger.error("Firefox directory not found in any of the expected locations")
            return None

        # Firefox profiles configuration file path
        conf_path = os.path.join(firefox_path, "profiles.ini")

        # Debug
        logger.debug("Config path %s" % conf_path)
        if not os.path.exists(conf_path):
            logger.error("Firefox profiles.ini not found")
            return None

        # Profile config parse
        profile = configparser.RawConfigParser()
        profile.read(conf_path)
        
        # Try to get the path from different profile sections
        prof_path = None
        for section in profile.sections():
            if section.startswith("Profile") and profile.has_option(section, "Path"):
                prof_path = profile.get(section, "Path")
                break
        
        if not prof_path:
            logger.error("Could not find a valid profile path in profiles.ini")
            return None

        # Sqlite db directory path
        sql_path = os.path.join(firefox_path, prof_path)
        sql_path = os.path.join(sql_path, "places.sqlite")

        # Debug
        logger.debug("Sql path %s" % sql_path)
        if not os.path.exists(sql_path):
            logger.error("Firefox places.sqlite not found")
            return None

        return sql_path

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
