import argparse
import configparser

from db import SQLiteDB
from feeds.cpp import CryptoPricePredictions



def cpp_downloader():
    
    db = SQLiteDB(db=config['database']['dbname'])
    cpp = CryptoPricePredictions(config=config, db=db)
    raw_data = cpp.download()
    cpp.transform(raw_data=raw_data)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="collector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="python collector.py --config=/path/to/config.ini"
    )

    parser.add_argument(
        '--downloader',
        dest='downloader',
        type=str,
        help='downloader type'
    )

    parser.add_argument(
        '--config',
        dest='config',
        type=str,
        help='config path'
    )

    args = parser.parse_args()
    config_path = "/opt/config.ini"
    if args.config:
        config_path = args.config

    config = configparser.ConfigParser()
    config.read(config_path)

    if args.downloader == "cpp":
        cpp_downloader()
    else:
        print(f"Not supported..")
