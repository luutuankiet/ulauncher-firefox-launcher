def __init__(self):
    #   Results order
    self.order = None

    #   Results number
    self.limit = None

    #   Set database location
    db_location = self.searchPlaces()
    
    if db_location is None:
        logger.error("Could not find Firefox places.sqlite database")
        # Create an in-memory SQLite database as a fallback
        self.conn = sqlite3.connect(":memory:")
        self.conn.create_function("hostname", 1, self.__getHostname)
        return

    #   Temporary file
    #   Using FF63 the DB was locked for exclusive use of FF
    temporary_db_location = tempfile.mktemp()
    shutil.copyfile(db_location, temporary_db_location)

    #   Open Firefox database
    self.conn = sqlite3.connect(temporary_db_location)

    #   External functions
    self.conn.create_function("hostname", 1, self.__getHostname)
