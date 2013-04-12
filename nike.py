#!/usr/bin/python
'''Nike - Just Fucking Do It

Copyright (c) 2013 Joseph Henke

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell 
copies of the Software, and to permit persons to whom the Software is furnished
to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR 
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE 
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER 
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, 
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE 
SOFTWARE.
'''

import os, sys, pickle
from datetime import date
from datetime import datetime

class Nike(object):
    '''environment'''

    def __init__(self, path):
        self.path = path
        if os.path.exists(path):
            self.load_tasks()
        else:
            self.tasks = []

    def load_tasks(self):
        self.tasks = []
        for line in open(self.path, 'r'):
            data = line.strip().split('|')
            if len(data) == 3:
                title, start_date, end_date = data[0], int(data[1]), int(data[2])
                self.tasks.append(DatedTask(title, start_date, end_date))
            elif len(data) == 6:
                title, start_date, end_date, weekly_start, weekly_end, completed_until = data[0], int(data[1]), int(data[2]), int(data[3]), int(data[4]), int(data[5])
                task = RecurringTask(title, start_date, end_date, weekly_start, weekly_end)
                task.completed_until = completed_until
                self.tasks.append(task)

    def loop(self):
        width = 3
        while True:
            self.save_tasks()
            self.show(width)
            try:
                com = raw_input("> ")
                if com == 'add':
                    title = raw_input("title> ")
                    bounds = raw_input("bounds?> ")
                    if len(bounds) == 0:
                        self.add(title)
                        continue
                    start_date, end_date = bounds.split(' ')
                    start_date = parse_date(start_date)
                    end_date = parse_date(end_date)
                    days = 'MTWRFSN'
                    
                    weekdays = raw_input("%s?> " % (days, ))
                    if len(weekdays) == 0:
                        self.add(title, (start_date, end_date))
                        continue
                    weekly_start, weekly_end = weekdays.split(' ')
                    weekly_start = days.index(weekly_start)
                    weekly_end = days.index(weekly_end)
                    self.add(title, (start_date, end_date), (weekly_start, weekly_end))

                elif com == 'mv':
                    i = int(raw_input("shift index> "))
                    amount = int(raw_input("shift amount> "))
                    self.shift(i, amount)
                elif com == 'extend':
                    i = int(raw_input("extend index> "))
                    amount = int(raw_input("extend amount> "))
                    self.extend(i, amount)
                elif com == 'rm':
                    i = int(raw_input("rm index> "))
                    self.rm(i)
                elif com == 'close':
                    i = int(raw_input("close index> "))
                    self.close(i)
                elif com == 'q':
                    break
                elif com == 'show':
                    x = int(raw_input("width> "))
                    width = x
                elif com.startswith('/'):
                    search = com[1:].lower()
                    save = self.tasks
                    self.tasks = [task for task in save if search in task.title.lower()]
                    self.show(width)
                    raw_input()
                    self.tasks = save
                elif com == 'backup':
                    self.save_tasks("/Users/jdhenke/.tasks_backup")
            except Exception as e:
                print "ERROR: %s" % (e, )

    def show(self, n=4):
        '''shows [today, today+n)'''
        # get blocks
        window_start_date = date.today().toordinal()
        window_end_date = window_start_date + n
        blocks = []
        for i, task in enumerate(self.tasks):
            blocks += [block + (i, ) for block in task.get_blocks(window_start_date, window_end_date)]
        blocks.sort()
        # print blocks
        col_width = 8
        print '|' + '-' * 29 + '|' + '|'.join([str(date.fromordinal(i).strftime(" %a ")).center(col_width - 1, '=') for i in xrange(window_start_date, window_end_date)])
        for left, right, text, i in blocks:
            text = ("%s %s" % (str(i).ljust(2), text))[:30].ljust(30)
            left_width = col_width * left
            right_width = col_width * (n - right)
            text_width = col_width * (right - left)
            print text +\
                ' ' * left_width +\
                (' %i ' % (i, )).center(text_width, '-') +\
                ' ' * right_width

    def save_tasks(self, path=None):
        if path is None:
            path = self.path
        f = open(path, 'w')
        for task in self.tasks:
            f.write("%s\n" % (task.to_file()))
        f.close()

    def add(self, title, (start_date, end_date) = (None, None), (weekly_start, weekly_end) = (None, None)):
        if start_date is None:
            start_date = date.today().toordinal()
            end_date = start_date + 1
            task = DatedTask(title, start_date, end_date)
        elif weekly_start is None:
            task = DatedTask(title, start_date, end_date)
        else:
            task = RecurringTask(title, start_date, end_date, weekly_start, weekly_end)
        self.tasks.append(task)
    
    def rm(self, i):
        del self.tasks[i]

    def close(self, i):
        task = self.tasks[i]
        if isinstance(task, RecurringTask):
            if task.close():
                self.rm(i)
        else:
            self.rm(i)

    def shift(self, i, x):
        self.tasks[i].shift(x)

    def extend(self, i, x):
        self.tasks[i].extend(x)

class DatedTask(object):
    def __init__(self, title, start_date, end_date):
        self.title = title
        self.start_date = start_date
        self.end_date = end_date

    def get_blocks(self, window_start_date, window_end_date):
        if self.start_date < window_end_date:
            # so should display block
            left = max(self.start_date, window_start_date) - window_start_date
            right = min(self.end_date, window_end_date) - window_start_date
            text = str(self)
            # TODO: revise to fit underlying conceptual model of this function
            if left >= right: # over end
                left = 0
                right = 1
                text = "!! " + text
            return [(left, right, text)]
        return []

    def shift(self, x):
        self.start_date += x
        self.end_date += x

    def extend(self, x):
        self.end_date += x

    def to_file(self):
        return '|'.join([self.title, str(self.start_date), str(self.end_date)])

    def __str__(self):
        return self.title

class RecurringTask(DatedTask):
    def __init__(self, title, start_date, end_date, weekly_start, weekly_end):
        super(RecurringTask, self).__init__(title, start_date, end_date)
        self.weekly_start = weekly_start
        self.weekly_end = weekly_end
        self.completed_until = self.start_date +\
            (self.weekly_start - date.fromordinal(self.start_date).weekday()) % 7

    def get_blocks(self, window_start_date, window_end_date):
        # find first live instance
        start = self.completed_until
        end = start + (self.weekly_end + 7 - self.weekly_start) % 7
        blocks = []
        instance = DatedTask(self.title, start, end)
        current_blocks = instance.get_blocks(window_start_date, window_end_date)
        while len(current_blocks) > 0 and end <= self.end_date:
            blocks += current_blocks
            start += 7
            end += 7
            instance = DatedTask(self.title , start, end)
            current_blocks = instance.get_blocks(window_start_date, window_end_date)
        return blocks

    def close(self):
        self.completed_until += 7
        return self.completed_until >= self.end_date

    def shift(self, x):
        pass

    def expand(self, x):
        pass
        
    def to_file(self):
        return '|'.join([self.title, str(self.start_date), str(self.end_date), str(self.weekly_start), str(self.weekly_end), str(self.completed_until)])

def parse_date(s):
    return date.today().toordinal() + int(s)

if __name__ == '__main__':
    nike = Nike("/Users/jdhenke/.tasks")
    nike.loop()
