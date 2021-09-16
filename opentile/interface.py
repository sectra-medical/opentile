from abc import ABCMeta, abstractmethod
from functools import cached_property
from pathlib import Path
from typing import List, Tuple, Iterator

from tifffile.tifffile import FileHandle, TiffFile, TiffPage, TiffPageSeries

from opentile.geometry import Point, Region, Size, SizeMm


class TiledPage(metaclass=ABCMeta):
    def __init__(
        self,
        page: TiffPage,
        fh: FileHandle
    ):
        """Abstract class for getting tiles from TiffPage.

        Parameters
        ----------
        page: TiffPage
            TiffPage to get tiles from.
        fh: FileHandle
            FileHandle for reading data.
        """
        self._page = page
        self._fh = fh

    @property
    def page(self) -> TiffPage:
        """Return source TiffPage."""
        return self._page

    @property
    def default_z(self) -> float:
        return 0.0

    @property
    def default_path(self) -> str:
        return '0'

    @property
    @abstractmethod
    def pyramid_index(self) -> int:
        raise NotImplementedError

    @property
    @abstractmethod
    def image_size(self) -> Size:
        raise NotImplementedError

    @property
    @abstractmethod
    def tile_size(self) -> Size:
        raise NotImplementedError

    @property
    @abstractmethod
    def tiled_size(self) -> Size:
        raise NotImplementedError

    @property
    @abstractmethod
    def pixel_spacing(self) -> SizeMm:
        raise NotImplementedError

    @abstractmethod
    def get_tile(self, tile: Tuple[int, int]) -> bytes:
        raise NotImplementedError

    def get_tiles(self, tiles: List[Tuple[int, int]]) -> Iterator[List[bytes]]:
        """Return iterator of list of bytes for tile positions.

        Parameters
        ----------
        tile_positions: List[Tuple[int, int]]
            Tile positions to get.

        Returns
        ----------
        bytes
            Produced tile at position.
        """
        return (
            [self.get_tile(tile)] for tile in tiles
        )

    def close(self) -> None:
        """Close filehandle."""
        self._fh.close()

    def pretty_str(
        self,
        indent: int = 0,
        depth: int = None
    ) -> str:
        return str(self)

    @cached_property
    def tiled_region(self) -> Region:
        """Tile region covering the TiledPage."""
        return Region(position=Point(0, 0), size=self.tiled_size - 1)

    def valid_tiles(self, region: Region) -> bool:
        """Check if tile region is inside tile geometry and z coordinate and
        optical path exists.

        Parameters
        ----------
        region: Region
            Tile region.
        """
        return region.is_inside(self.tiled_region)


class Tiler:
    def __init__(self, filepath: Path):
        self._filepath = filepath
        self._tiff_file = TiffFile(self._filepath)
        self._volume_series_index: int = None
        self._overview_series_index: int = None
        self._label_series_index: int = None

    @cached_property
    def base_page(self) -> TiffPage:
        """Return base pyramid level in volume series."""
        return self.series[self._volume_series_index].pages[0]

    @cached_property
    def base_size(self) -> Size:
        """Return size of base pyramid level in volume series."""
        return Size(self.base_page.shape[1], self.base_page.shape[0])

    @property
    def series(self) -> List[TiffPageSeries]:
        """Return contained TiffPageSeries."""
        return self._tiff_file.series

    @property
    def levels(self) -> List[TiledPage]:
        """Return list of volume level TiledPages."""
        if self._volume_series_index is None:
            return []
        return [
            self.get_level(level_index, page_index)
            for level_index, level
            in enumerate(self.series[self._volume_series_index].levels)
            for page_index, page in enumerate(level.pages)
        ]

    @property
    def labels(self) -> List[TiledPage]:
        """Return list of label TiledPages."""
        if self._label_series_index is None:
            return []
        return [
            self.get_label(level_index, page_index)
            for level_index, level
            in enumerate(self.series[self._label_series_index].levels)
            for page_index, page in enumerate(level.pages)
        ]

    @property
    def overviews(self) -> List[TiledPage]:
        """Return list of overview TiledPages."""
        if self._overview_series_index is None:
            return []
        return [
            self.get_overview(level_index, page_index)
            for level_index, level
            in enumerate(self.series[self._overview_series_index].levels)
            for page_index, page in enumerate(level.pages)
        ]

    @abstractmethod
    def get_page(self, series: int, level: int, page: int) -> TiledPage:
        raise NotImplementedError

    def close(self) -> None:
        """CLose tiff-file."""
        self._tiff_file.close()

    def get_tile(
        self,
        series: int,
        level: int,
        page: int,
        tile_position: Tuple[int, int]
    ) -> bytes:
        """Return tile for tile position x and y.

        Parameters
        ----------
        series: int
            Series of page to get tile from.
        level: int
            Level of page to get tile from.
        page: int
            Page to get tile from.
        tile_position: Tuple[int, int]
            Position of tile to get.

        Returns
        ----------
        bytes
            Tile at position.
        """
        tiled_page = self.get_page(series, level, page)
        return tiled_page.get_tile(tile_position)

    def get_level(
        self,
        level: int,
        page: int = 0
    ) -> TiledPage:
        """Return TiledPage for level in volume series.

        Parameters
        ----------
        level: int
            Level to get.
        page: int
            Index of page to get.

        Returns
        ----------
        TiledPage
            Level TiledPage.
        """
        return self.get_page(self._volume_series_index, level, page)

    def get_label(
        self,
        index: int = 0,
        page: int = 0
    ) -> TiledPage:
        """Return TiledPage for label in label series.

        Parameters
        ----------
        index: int
            Index of label to get.
        page: int
            Index of page to get.

        Returns
        ----------
        TiledPage
            Label TiledPage.
        """
        return self.get_page(self._label_series_index, index, page)

    def get_overview(
        self,
        index: int = 0,
        page: int = 0
    ) -> TiledPage:
        """Return TiledPage for overview in overview series.

        Parameters
        ----------
        index: int
            Index of overview to get.
        page: int
            Index of page to get.

        Returns
        ----------
        TiledPage
            Overview TiledPage.
        """
        return self.get_page(self._overview_series_index, index, page)
