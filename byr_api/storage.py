
import json
import logging
from copy import deepcopy
from pathlib import Path
from datetime import datetime, timedelta, date

MAGICKEY = "__Key"


def dict_changed(old, new):
    ret = str(old) != str(new)
    return ret
    
class DateEncoder(json.JSONEncoder):  
    def default(self, obj):  
        if isinstance(obj, datetime):  
            return obj.strftime('%Y-%m-%d %H:%M:%S')   

        return super().default(self, obj) 

class SpiderStorage:
    def __init__(self, storage_path="./storage.dat", read=True, write=True):
        self.read_ = read
        self.write_ = write
        self.d_ = {}
        self.key_ = set()
        self.storage_path_ = Path(storage_path)
        self.fp_ = self.load_()

    def __getitem__(self, k):
        return self.d_[k]

    def __setitem__(self, k, v):
        # print("call __setitem__(k=%r, v=%r)" % (k, v))
        assert isinstance(v, dict)
        assert MAGICKEY not in v, v
        assert self.write_

        old = None

        if self.read_:
            old = self.d_.get(k)
            if old: assert MAGICKEY not in old, old
            self.d_[k] = v

        if old is None or dict_changed(old, v):
            # print("old is None? %s" % (old is None))
            v = v.copy()
            v[MAGICKEY] = k
            vv = json.dumps(v, cls=DateEncoder, ensure_ascii=False, separators=(',',':'))
            self.fp_.write(vv + "\n")
            # self.fp_.flush()


    def get(self, k, default=None):
        return self.d_.get(k, default)

    def load_(self):
        if not self.storage_path_.exists():
            self.storage_path_.touch()

        self.d_.clear()

        for line in self.storage_path_.open("r", encoding="utf-8"):
            if line.strip() and self.read_:
                try:
                    v = json.loads(line)
                    self.d_[v.pop(MAGICKEY)] = v
                except json.decoder.JSONDecodeError:
                    logging.info("load line fail: %s", line)

        if self.write_:
            return self.storage_path_.open("a+", encoding="utf-8")

    def commit(self):
        pass

    def create_index(self):
        name, suffix = str(self.storage_path_).rsplit(".", 1)
        index_name = name + ".idx"
        self.index_path_ = Path(index_name)
        new_reader = open(str(self.storage_path_), encoding="utf-8")

        writer = self.index_path_.open("w", encoding="utf-8")

        while True:
            pos = new_reader.tell()
            line = new_reader.readline()
            v = json.loads(line)
            k = v[MAGICKEY]

            writer.write(f'{{ {MAGICKEY}: {k}, "pos": {pos} }}')


class SpiderQueue:
    def __init__(self, storage_path, write=False):
        self.counter = 0
        self.write_ = write

        self.storage_path_ = Path(storage_path)
        self.fp_ = self.load_()

    def append(self, v):
        counter = self.counter
        v["counter"] = counter
        self[counter] = v
        self.counter += 1

    def __len__(self):
        return self.counter

    def __iter__(self):

        class _I:
            def __init__(self, parent):
                self.parent_ = parent
                self.get_counter_ = 0
                self.fp_ = parent.storage_path_.open("r", encoding="utf-8")
            def __next__(self):
                if self.get_counter_ >= self.parent_.counter:
                    raise StopIteration()
                while True:
                    l = self.fp_.readline()
                    if l == "":
                        raise Exception()
                    v = json.loads(l)
                    k = v.pop(MAGICKEY)

                    if k == "get_counter":
                        continue
                    self.get_counter_ += 1
                    return v

        return _I(self)

    def load_(self):
        if not self.storage_path_.exists():
            self.storage_path_.touch()

        for line in self.storage_path_.open("r", encoding="utf-8"):
            if line.strip():
                v = json.loads(line)
                k = v.pop(MAGICKEY)

                if k != "get_counter":
                    self.counter += 1

        if self.write_:
            return self.storage_path_.open("a+", encoding="utf-8")





if __name__ == '__main__':
    storage = SpiderStorage("./test.dat")
    print(storage.d_)
    storage["ds"] = {"1": "d"}
    print(storage.d_)
    storage["ds"] = {"1": "d"}
    print(storage.d_)
    
