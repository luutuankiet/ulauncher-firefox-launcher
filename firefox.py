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
        """Find the Firefox places.sqlite database file"""
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
        
        # First try using profiles.ini
        for base_path in possible_base_paths:
            if not os.path.exists(base_path):
                logger.debug(f"Path does not exist: {base_path}")
                continue
                
            conf_path = os.path.join(base_path, "profiles.ini")
            if not os.path.exists(conf_path):
                logger.debug(f"profiles.ini not found at: {conf_path}")
                continue
                
            logger.debug(f"Found profiles.ini at: {conf_path}")
            
            try:
                # Parse the profiles.ini file
                profile = configparser.RawConfigParser()
                profile.read(conf_path)
                
                # Try to find the default profile
                for section in profile.sections():
                    if not section.startswith("Profile"):
                        continue
                        
                    # Skip if no Path option
                    if not profile.has_option(section, "Path"):
                        continue
                        
                    prof_path = profile.get(section, "Path")
                    
                    # Check if this is the default profile
                    is_default = (profile.has_option(section, "Default") and 
                                 profile.get(section, "Default") == "1")
                    
                    # Determine if the path is relative or absolute
                    is_relative = True
                    if profile.has_option(section, "IsRelative"):
                        is_relative = profile.get(section, "IsRelative") == "1"
                    
                    # Construct the full path to the profile
                    if is_relative:
                        profile_path = os.path.join(base_path, prof_path)
                    else:
                        profile_path = prof_path
                    
                    # Check if places.sqlite exists in this profile
                    places_path = os.path.join(profile_path, "places.sqlite")
                    if os.path.exists(places_path):
                        logger.debug(f"Found places.sqlite at: {places_path}")
                        return places_path
                        
                    # If this is the default profile but places.sqlite doesn't exist,
                    # log it and continue searching
                    if is_default:
                        logger.debug(f"Default profile found but places.sqlite missing: {places_path}")
            
            except Exception as e:
                logger.error(f"Error parsing profiles.ini at {conf_path}: {str(e)}")
        
        # If we couldn't find it using profiles.ini, try direct search
        logger.debug("Trying direct search for places.sqlite...")
        
        # Direct search in common profile locations
        for base_path in possible_base_paths:
            if not os.path.exists(base_path):
                continue
                
            # Look for directories that might be profile directories
            try:
                for item in os.listdir(base_path):
                    item_path = os.path.join(base_path, item)
                    
                    # Skip if not a directory
                    if not os.path.isdir(item_path):
                        continue
                        
                    # Check if this looks like a Firefox profile (has .default or contains random characters)
                    if (item.endswith('.default') or 
                        item.endswith('.default-release') or 
                        (len(item) > 8 and '.' in item)):
                        
                        places_path = os.path.join(item_path, "places.sqlite")
                        if os.path.exists(places_path):
                            logger.debug(f"Found places.sqlite directly at: {places_path}")
                            return places_path
            except Exception as e:
                logger.error(f"Error searching directory {base_path}: {str(e)}")
        
        # Specific check for your known path
        specific_path = os.path.join(home, "snap/firefox/common/.mozilla/firefox/yq7q3frd.default/places.sqlite")
        if os.path.exists(specific_path):
            logger.debug(f"Found places.sqlite at specific path: {specific_path}")
            return specific_path
            
        # If we get here, we couldn't find the places.sqlite file
        logger.error("Firefox places.sqlite not found in any location")
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
