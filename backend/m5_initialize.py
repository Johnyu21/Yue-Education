"""Compatibility command. All schema changes now use the central migration chain."""
import argparse
from app.db.migrate import migrate,DIRECTORY
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    if args.apply:print('Applied migrations:',migrate())
    else:print('Pending migration source directory:',DIRECTORY)
