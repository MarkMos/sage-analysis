"""
This module contains the ``Model`` class.  The ``Model`` class contains all the data
paths, cosmology etc for calculating galaxy properties.

To read **SAGE** data, we make use of specialized Data Classes (e.g.,
:py:class:`~sage_analysis.sage_binary.SageBinaryData`
and:py:class:`~sage_analysis.sage_hdf5.SageHdf5Data`). We refer to
:doc:`../user/data_class` for more information about adding your own Data Class to ingest
data.

To calculate (and plot) extra properties from the **SAGE** output, we refer to
:doc:`../user/calc.rst` and :doc:`../user/plotting.rst`.
"""

import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional

import numpy as np

try:
    from tqdm import tqdm
except ImportError:
    print("Package 'tqdm' not found. Not showing pretty progress bars :(")
else:
    pass

logger = logging.getLogger(__name__)


class Model(object):
    """
    Handles all the galaxy data (including calculated properties) for a ``SAGE`` model.

    The ingestion of data is handled by inidivudal Data Classes (e.g.,
    :py:class:`~sage_analysis.sage_binary.SageBinaryData` and :py:class:`~sage_analysis.sage_hdf5.SageHdf5Data`).
    We refer to :doc:`../user/data_class` for more information about adding your own Data Class to ingest data.
    """

    def __init__(
        self,
        sage_file: str,
        sage_output_format: Optional[str],
        label: Optional[str],
        first_file_to_analyze: int,
        last_file_to_analyze: int,
        num_sage_output_files: Optional[int],
        random_seed: Optional[int],
        IMF: str,
        plot_toggles: Dict[str, bool],
        plots_that_need_smf: List[str],
        sample_size: int = 1000,
        sSFRcut: float = -11.0,
    ):
        """
        Sets the galaxy path and number of files to be read for a model. Also initialises
        the plot toggles that dictates which properties will be calculated.

        Parameters
        ----------

        label : str, optional
            The label that will be placed on the plots for this model.  If not specified, will use ``FileNameGalaxies``
            read from ``sage_file``.

        sage_output_format : str, optional
            If not specified will use the ``OutputFormat`` read from ``sage_file``.

        num_sage_output_files : int, optional
            Specifies the number of output files that were generated by running **SAGE**.  This can be different to the
            range specified by [first_file_to_analyze, last_file_to_analyze].

            Notes
            -----
            This variable only needs to be specified if ``sage_output_format`` is ``sage_binary``.

        sample_size: int, optional
            Specifies the length of the :py:attr:`~properties` attributes stored as 1-dimensional
            :obj:`~numpy.ndarray`.  These :py:attr:`~properties` are initialized using
            :py:meth:`~init_scatter_properties`.

        sSFRcut : float, optional
            The specific star formation rate above which a galaxy is flagged as "star forming".  Units are log10.
        """

        self._sage_file = sage_file
        self._IMF = IMF
        self._label = label
        self._sage_output_format = sage_output_format
        self._first_file_to_analyze = first_file_to_analyze
        self._last_file_to_analyze = last_file_to_analyze
        self._random_seed = random_seed
        self._plot_toggles = plot_toggles
        self._plots_that_need_smf = plots_that_need_smf

        self._sample_size = sample_size
        self._sSFRcut = sSFRcut

        self._bins = {}
        self._properties = defaultdict(dict)

        if num_sage_output_files is None and sage_output_format == "sage_binary":
            raise RuntimeError(
                "When analysing binary SAGE output, the number of output files generated by SAGE must be specified."
            )
        else:
            self._num_sage_output_files = num_sage_output_files

        if (first_file_to_analyze is None or last_file_to_analyze is None) and sage_output_format == "sage_binary":
            raise RuntimeError(
                "When analysing binary SAGE output, the first and last SAGE output file to analyze must be specified."
            )

    @property
    def sage_file(self) -> str:
        """
        str : The path to where the **SAGE** ``.ini`` file is located.
        """
        return self._sage_file

    @property
    def num_sage_output_files(self):
        """
        int: The number of files that **SAGE** wrote.  This will be equal to the number of
        processors the **SAGE** ran with.

        Notes
        -----
        If :py:attr:`~sage_output_format` is ``sage_hdf5``, this attribute is not required.
        """
        return self._num_sage_output_files

    @property
    def hubble_h(self):
        """
        float: Value of the fractional Hubble parameter. That is, ``H = 100*hubble_h``.
        """
        return self._hubble_h

    @property
    def box_size(self):
        """
        float: Size of the simulation box. Units are Mpc/h.
        """
        return self._box_size

    @property
    def volume(self):
        """
        volume: Volume spanned by the trees analyzed by this model.  This depends upon the
        number of files processed, ``[:py:attr:`~first_file_to_analyze`, :py:attr:`~last_file_to_analyze`]``,
        relative to the total number of files the simulation spans over,
        :py:attr:`~num_sim_tree_files`.

        Notes
        -----

        This is **not** necessarily :py:attr:`~box_size` cubed. It is possible that this
        model is only analysing a subset of files and hence the volume will be less.
        """
        return self._volume

    @volume.setter
    def volume(self, vol):

        if vol > pow(self.box_size, 3):
            print("The volume analyzed by a model cannot exceed the volume of the box "
                  "itself.  Error was encountered for the following model.")
            print(self)
            raise ValueError

        self._volume = vol

    @property
    def redshifts(self):
        """
        :obj:`~numpy.ndarray`: Redshifts for this simulation.
        """
        return self._redshifts

    @property
    def sage_output_format(self):
        """
        {``"sage_binary"``, ``"sage_binary"``}: The output format **SAGE** wrote in.
        A specific Data Class (e.g., :py:class:`~sage_analysis.sage_binary.SageBinaryData`
        and :py:class:`~sage_analysis.sage_hdf5.SageHdf5Data`) must be written and
        used for each :py:attr:`~sage_output_format` option. We refer to
        :doc:`../user/data_class` for more information about adding your own Data Class to ingest
        data.
        """
        return self._sage_output_format

    @property
    def base_sage_data_path(self) -> str:
        """
        string: Base path to the output data. This is the path without specifying any extra information about redshift
        or the file extension itself.
        """
        return self._base_sage_data_path

    @property
    def sage_data_path(self) -> str:
        """
        string: Path to the output data. If :py:attr:`~sage_output_format` is
        ``sage_binary``, files read must be labelled :py:attr:`~sage_data_path`.XXX.
        If :py:attr:`~sage_output_format` is ``sage_hdf5``, the file read will be
        :py:attr:`~sage_data_path` and the groups accessed will be Core_XXX at snapshot
        :py:attr:`~snapshot`. In both cases, ``XXX`` represents the numbers in the range
        [:py:attr:`~first_file_to_analyze`, :py:attr:`~last_file_to_analyze`] inclusive.
        """
        return self._sage_data_path

    @property
    def output_path(self):
        """
        string: Path to where some plots will be saved. Used for
        :py:meth:`~sage_analysis.plots.plot_spatial_3d`.
        """
        return self._output_path

    @property
    def IMF(self):
        """
        {``"Chabrier"``, ``"Salpeter"``}: The initial mass function.
        """
        return self._IMF

    @IMF.setter
    def IMF(self, IMF):
        # Only allow Chabrier or Salpeter IMF.
        allowed_IMF = ["Chabrier", "Salpeter"]
        if IMF not in allowed_IMF:
            raise ValueError(
                "Value of IMF selected ({0}) is not allowed. Only {1} are "
                "allowed.".format(IMF, allowed_IMF)
            )
        self._IMF = IMF

    @property
    def label(self):
        """
        string: Label that will go on axis legends for this :py:class:`~Model`.
        """
        return self._label

    @property
    def first_file_to_analyze(self):
        """
        int: The first *SAGE* sub-file to be read. If :py:attr:`~sage_output_format` is
        ``sage_binary``, files read must be labelled :py:attr:`~sage_data_path`.XXX.
        If :py:attr:`~sage_output_format` is ``sage_hdf5``, the file read will be
        :py:attr:`~sage_data_path` and the groups accessed will be Core_XXX. In both cases,
        ``XXX`` represents the numbers in the range
        [:py:attr:`~first_file_to_analyze`, :py:attr:`~last_file_to_analyze`] inclusive.
        """
        return self._first_file_to_analyze

    @property
    def last_file_to_analyze(self):
        """
        int: The last **SAGE** sub-file to be read. If :py:attr:`~sage_output_format` is
        ``sage_binary``, files read must be labelled :py:attr:`~sage_data_path`.XXX.
        If :py:attr:`~sage_output_format` is ``sage_hdf5``, the file read will be
        :py:attr:`~sage_data_path` and the groups accessed will be Core_XXX. In both cases,
        ``XXX`` represents the numbers in the range
        [:py:attr:`~first_file_to_analyze`, :py:attr:`~last_file_to_analyze`] inclusive.
        """
        return self._last_file_to_analyze

    @property
    def snapshot(self):
        """
        int: Specifies the snapshot to be read. If :py:attr:`~sage_output_format` is
        ``sage_hdf5``, this specifies the HDF5 group to be read. Otherwise, if
        :py:attr:`sage_output_format` is ``sage_binary``, this attribute will be used to
        index :py:attr:`~redshifts` and generate the suffix for :py:attr:`~sage_data_path`.
        """
        return self._snapshot

    @property
    def bins(self):
        """
        dict [string, :obj:`~numpy.ndarray` ]: The bins used to bin some
        :py:attr:`properties`. Bins are initialized through
        :py:meth:`~Model.init_binned_properties`. Key is the name of the bin,
        (``bin_name`` in :py:meth:`~Model.init_binned_properties` ).
        """
        return self._bins

    @property
    def properties(self):
        """
        dict [string, dict [string, :obj:`~numpy.ndarray` ]] or dict[string, dict[string, float]: The galaxy properties
        stored across the input files and snapshots. These properties are updated within the respective
        ``calc_<plot_toggle>`` functions.

        The outside key is ``"snapshot_XX"`` where ``XX`` is the snapshot number for the property. The inner key is the
        name of the proeprty (e.g., ``"SMF"``).
        """
        return self._properties

    @property
    def sample_size(self):
        """
        int: Specifies the length of the :py:attr:`~properties` attributes stored as 1-dimensional
        :obj:`~numpy.ndarray`.  These :py:attr:`~properties` are initialized using
        :py:meth:`~init_scatter_properties`.
        """
        return self._sample_size

    @property
    def num_gals_all_files(self):
        """
        int: Number of galaxies across all files. For HDF5 data formats, this represents
        the number of galaxies across all `Core_XXX` sub-groups.
        """
        return self._num_gals_all_files

    @property
    def parameter_dirpath(self):
        """
        str : The directory path to where the **SAGE** paramter file is located.  This is only the base directory path
        and does not include the name of the file itself.
        """
        return self._parameter_dirpath

    @property
    def random_seed(self) -> Optional[int]:
        """
        Optional[int] : Specifies the seed used for the random number generator, used to select galaxies for plotting
        purposes. If ``None``, then uses default call to :func:`~numpy.random.seed`.
        """
        return self._random_seed

    @property
    def plots_that_need_smf(self) -> List[str]:
        """
        list of ints : Specifies the plot toggles that require the stellar mass function to be properly computed and
        analyzed. For example, plotting the quiescent fraction of galaxies requires knowledge of the total number of
        galaxies. The strings here must **EXACTLY** match the keys in :py:attr:`~plot_toggles`.
        """
        return self._plots_that_need_smf

    @property
    def plot_toggles(self):
        """
        dict[str, bool] : Specifies which plots should be created for this model. This will control which properties
        should be calculated; e.g., if no stellar mass function is to be plotted, the stellar mass function will not be
        computed.
        """
        return self._plot_toggles

    @property
    def calculation_functions(self):
        """
        dict[str, tuple[func, dict[str, any]]] : A dictionary of functions that are used to compute the properties of
        galaxies.  Here, the string is the name of the toggle (e.g., ``"SMF"``), the value is a tuple
        containing the function itself (e.g., ``calc_SMF()``), and another dictionary which specifies any optional
        keyword arguments to that function with keys as the name of variable (e.g., ``"calc_sub_populations"``) and
        values as the variable value (e.g., ``True``).
        """
        return self._calculation_functions

    @property
    def sSFRcut(self) -> float:
        """
        float : The specific star formation rate above which a galaxy is flagged as "star forming".  Units are log10.
        """
        return self._sSFRcut

    def __repr__(self):

        string = "========================\n" \
                f"Model {self._label}\n" \
                f"SAGE File: {self._sage_file}\n" \
                f"SAGE Output Format: {self._sage_output_format}\n" \
                f"First file to read: {self._first_file_to_analyze}\n" \
                f"Last file to read: {self._last_file_to_analyze}\n" \
                 "========================"

        return string

    def init_binned_properties(
        self,
        bin_low: float,
        bin_high: float,
        bin_width: float,
        bin_name: str,
        property_names: List[str],
        snapshot: int
    ):
        """
        Initializes the :py:attr:`~properties` (and respective :py:attr:`~bins`) that will
        binned on some variable.  For example, the stellar mass function (SMF) will
        describe the number of galaxies within a stellar mass bin.

        :py:attr:`~bins` can be accessed via ``Model.bins["bin_name"]`` and are
        initialized as :obj:`~numpy.ndarray`. :py:attr:`~properties` can be accessed via
        ``Model.properties["property_name"]`` and are initialized using
        :obj:`numpy.zeros`.

        Parameters
        ----------

        bin_low, bin_high, bin_width : floats
            Values that define the minimum, maximum and width of the bins respectively.
            This defines the binning axis that the ``property_names`` properties will be
            binned on.

        bin_name : string
            Name of the binning axis, accessed by ``Model.bins["bin_name"]``.

        property_names : list of strings
            Name of the properties that will be binned along the defined binning axis.
            Properties can be accessed using ``Model.properties["property_name"]``; e.g.,
            ``Model.properties["SMF"]`` would return the stellar mass function that is binned
            using the ``bin_name`` bins.

        snapshot : int
            The snapshot we're initialising the properties for.
        """

        # Parameters that define the specified binning axis.
        bins = np.arange(bin_low, bin_high + bin_width, bin_width)

        # Add the bins to the dictionary.
        self.bins[bin_name] = bins

        # When making histograms, the right-most bin is closed. Hence the length of the
        # produced histogram will be `len(bins)-1`.
        for my_property in property_names:
            self.properties[f"snapshot_{snapshot}"][my_property] = np.zeros(len(bins) - 1, dtype=np.float64)

    def init_scatter_properties(self, property_names: List[str], snapshot: int):
        """
        Initializes the :py:attr:`~properties` that will be extended as
        :obj:`~numpy.ndarray`. These are used to plot (e.g.,) a the star formation rate
        versus stellar mass for a subset of :py:attr:`~sample_size` galaxies. Initializes
        as empty :obj:`~numpy.ndarray`.

        Parameters
        ----------
        property_names : list of strings
            Name of the properties that will be extended as :obj:`~numpy.ndarray`.

        snapshot : int
            The snapshot we're initialising the properties for.
        """

        # Initialize empty arrays.
        for my_property in property_names:
            self.properties[f"snapshot_{snapshot}"][my_property] = np.array([])

    def init_single_properties(self, property_names: List[str], snapshot: int) -> None:
        """
        Initializes the :py:attr:`~properties` that are described using a single number.
        This is used to plot (e.g.,) a the sum of stellar mass across all galaxies.
        Initializes as ``0.0``.

        Parameters
        ----------
        property_names : list of strings
            Name of the properties that will be described using a single number.

        snapshot : int
            The snapshot we're initialising the properties for.
        """

        # Initialize as zeros.
        for my_property in property_names:
            self.properties[f"snapshot_{snapshot}"][my_property] = 0.0

    def calc_properties_all_files(
        self,
        calculation_functions,
        snapshot: int,
        close_file: bool = True,
        use_pbar: bool = True,
        debug: bool = False,
    ):
        """
        Calculates galaxy properties for all files of a single :py:class:`~Model`.

        Parameters
        ----------
        calculation_functions: dict [string, list(function, dict[string, variable])]
            Specifies the functions used to calculate the properties of this
            :py:class:`~Model`. The key of this dictionary is the name of the plot toggle.
            The value is a list with the 0th element being the function and the 1st
            element being a dictionary of additional keyword arguments to be passed to
            the function. The inner dictionary is keyed by the keyword argument names
            with the value specifying the keyword argument value.

            All functions in this dictionary for called after the galaxies for each
            sub-file have been loaded. The function signature is required to be
            ``func(Model, gals, <Extra Keyword Arguments>)``.

        snapshot : int
            The snapshot that we're calculating properties for.

        close_file: boolean, optional
            Some data formats have a single file data is read from rather than opening and
            closing the sub-files in :py:meth:`read_gals`. Hence once the properties are
            calculated, the file must be closed. This variable flags whether the data
            class specific :py:meth:`~close_file` method should be called upon completion of
            this method.

        use_pbar: Boolean, optional
            If set, uses the ``tqdm`` package to create a progress bar.

        debug: Boolean, optional
            If set, prints out extra useful debug information.
        """

        start_time = time.time()

        # Ensure that we're pointing at the correct snapshot. This allows the model path to point to the correct file.
        self.data_class.update_snapshot_and_data_path(self, snapshot)

        # First determine how many galaxies are in all files.
        self.data_class.determine_num_gals(self, snapshot)
        if self._num_gals_all_files == 0:
            logger.info(f"There were no galaxies associated with this model at Snapshot {self._snapshot}.")
            print(self._num_gals_all_files)
            return

        # If the user requested the number of galaxies plotted/calculated

        # The `tqdm` package provides a beautiful progress bar.
        try:
            if debug or not use_pbar:
                pbar = None
            else:
                pbar = tqdm(total=self._num_gals_all_files, unit="Gals", unit_scale=True)
        except NameError:
            pbar = None
        else:
            pass

        # Now read the galaxies and calculate the properties.
        for file_num in range(self.first_file_to_analyze, self.last_file_to_analyze + 1):

            # This is Data Class specific. Refer to the relevant module for implementation.
            gals = self.data_class.read_gals(self, file_num, snapshot, pbar=pbar, debug=debug)

            # We may have skipped a file.
            if gals is None:
                continue

            print(calculation_functions)
            self.calc_properties(calculation_functions, gals, snapshot)

        # Some data formats (e.g., HDF5) have a single file we read from.
        if close_file:
            self.data_class.close_file(self)

        end_time = time.time()
        duration = end_time - start_time

        if debug:
            print(
                "Took {0:.2f} seconds ({1:.2f} minutes)".format(duration, duration / 60.0)
            )
            print("")

    def calc_properties(self, calculation_functions, gals, snapshot: int):
        """
        Calculates galaxy properties for a single file of galaxies.

        Parameters
        ----------

        calculation_functions: dict [string, function]
            Specifies the functions used to calculate the properties. All functions in
            this dictionary are called on the galaxies. The function signature is required
            to be ``func(Model, gals)``

        gals: exact format given by the :py:class:`~Model` Data Class.
            The galaxies for this file.

        snapshot : int
            The snapshot that we're calculating properties for.

        Notes
        -----

        If :py:attr:`~sage_output_format` is ``sage_binary``, ``gals`` is a ``numpy``
        structured array. If :py:attr:`~sage_output_format`: is
        ``sage_hdf5``, ``gals`` is an open HDF5 group. We refer to
        :doc:`../user/data_class` for more information about adding your own Data Class to ingest data.
        """

        # Now check which plots the user is creating and hence decide which properties they need.
        for func, kwargs in calculation_functions.values():

            # **kwargs unpacks the `kwargs` dictionary, passing each keyword properly to the function.
            func(self, gals, snapshot, **kwargs)
