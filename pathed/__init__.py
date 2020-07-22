import os
from blake3 import blake3
from typing import List
from abc import ABC, abstractmethod

file_count = 0

class Pathed(ABC):
    """
    An abstract parent class for "pathed" (uniquely identified by a filesystem path) objects
    """
    def __init__(self, path: str, path_method, path_error, parent=None, hash_files=False):
        """
        :param path: The relative or absolute path to the Pathed object
        :param path_method: The method used to determine if the element is valid
        :param path_error: The error to raise if validation fails
        :param parent: The parent of this object
        :param hash_files: Whether or not files should be hashed automatically. Disabled by default.
        """
        if not path_method(path):
            raise path_error(path)

        # Private
        self.__parent: Pathed = parent
        self.__path: str = os.path.abspath(path)
        self.__name = self.__path.split(os.sep)[-1]
        self.__last_refreshed: float = -1
        self.__is_dir: bool = issubclass(self.__class__, Directory)
        self.__is_file: bool = issubclass(self.__class__, File)
        self.__created_at: float = os.path.getctime(self.__path)
        self.__last_modified: float = os.path.getmtime(self.__path)

        # Protected
        self.__hash_files: bool = hash_files

    @abstractmethod
    def refresh(self) -> bool:
        """
            Refreshes a Pathed object with the most recent changes on the filesystem
            :returns bool: Whether or not the object was refreshed (modified)
        """
        file_last_modified = os.path.getmtime(self.__path)
        refreshed = self.__last_modified != file_last_modified

        if refreshed:
            self.__last_modified = file_last_modified

        return refreshed

    @property
    def parent_dir(self):
        """:returns Directory: The Parent Directory or None"""
        return self.__parent

    @property
    def is_dir(self):
        """:returns bool: True if a Directory or its descendent otherwise False"""
        return self.__is_dir

    @property
    def is_file(self):
        """:returns bool: True if a File or its descendent, otherwise False"""
        return self.__is_file

    @property
    def name(self):
        """:returns str: The file or directory name without a preceding path (e.g. pathed.txt)"""
        return self.__name

    @property
    def _should_hash_files(self):
        """
        Protected Access
        :returns bool: If files should be hashed or not, should not be used outside of Pathed objects
        """
        return self.__hash_files

    @property
    def path(self):
        """:returns str: The absolute path to this object on the filesystem"""
        return self.__path

    def has_parent(self):
        return self.parent_dir is not None


class Directory(Pathed):
    """
    Extends the Pathed class to represent a filesystem Directory
    """
    def __init__(self, path: str, parent_dir=None, hash_files=False, recursive=False, recursive_depth=0):
        """
        :param path: The relative or absolute path to the Pathed object
        :param path_method: The method used to determine if the element is valid
        :param hash_files:
        :param recursive: Whether or not to recurse into child directories. Disabled by default.
        :param recursive_depth: The depth to recurse into child directories. A value of 0 will recurse until exhaustion. Implies recursive.
        """
        super().__init__(path, os.path.isdir, NotADirectoryError, parent_dir)
        self.__sub_dirs: List[Directory] = []
        self.__files: List[File] = []
        self.__empty: bool = False
        self.__recursive = recursive
        self.__recursive_depth = recursive_depth
        self.__populate()

    def __populate(self):
        global file_count

        items = os.listdir(self.path)
        if len(items) == 0:
            self.__empty = True

        for item in items:
            item_path = os.path.join(self.path, item)
            if os.path.isdir(item_path):
                if self.__recursive_depth >= 0:
                    self.__sub_dirs.append(Directory(item_path, self, self._should_hash_files, self.__recursive, self.__recursive_depth - 1))
            elif os.path.isfile(item_path):
                self.__files.append(File(item_path, self))
                file_count += 1
                print(file_count)
            else:
                raise EnvironmentError(f'Unknown Directory Element: {item_path}')

    @property
    def empty(self) -> bool:
        """:returns bool: True if the file has no contents, otherwise False"""
        return self.__empty

    def refresh(self) -> bool:
        """
        Extends the Pathed refresh method to include all sub-directories and files
        :returns  bool: Whether or not the file was refreshed.
        """
        refreshed = super().refresh()
        for sub_dir in self.__sub_dirs:
            refreshed = refreshed or sub_dir.refresh()
        for file in self.__files:
            refreshed = refreshed or file.refresh()

        return refreshed


class File(Pathed):
    """
    Extends the Pathed class to represent a filesystem File
    """

    def __init__(self, path: str, parent_dir):
        """
        :param name: The name of this file
        :param parent_dir: The parent directory in which this file resides
        """
        super().__init__(path, os.path.isfile, FileExistsError, parent_dir)
        self.__filesize: int
        self.__hash: float
        self.__calculate_hash_and_size()

    def __hash_file(self) -> str:
        with open(self.path, 'rb') as f:
            contents = f.read()
            return blake3(contents).hexdigest() if len(contents) > 0 else b''

    def __calculate_hash_and_size(self):
        if self._should_hash_files:
            self.__hash = self.__hash_file()

        self.__filesize = os.path.getsize(self.path)

    @property
    def filesize(self) -> int:
        """:returns int: The size of the file in bytes"""
        return self.__filesize

    @property
    def hash(self) -> str:
        """:returns str: The hash of this File's contents. Regenerated on each call if hash_files is False."""
        self.__calculate_hash_and_size()
        return self.__hash

    def refresh(self) -> bool:
        """
        Extends the Pathed refresh method to calculate the file hash if enabled.
        :returns  bool: Whether or not the file was refreshed.
        """
        refreshed = super().refresh()
        if self._should_hash_files:
            old_hash = self.__hash
            self.__calculate_hash_and_size()
            if old_hash != self.__hash:
                refreshed = True

        return refreshed
