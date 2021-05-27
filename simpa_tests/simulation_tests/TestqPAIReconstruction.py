# The MIT License (MIT)
#
# Copyright (c) 2021 Computer Assisted Medical Interventions Group, DKFZ
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated simpa_documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# FIXME temporary workaround for newest Intel architectures
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
from simpa.utils.path_manager import PathManager
import numpy as np
import os
import matplotlib.pyplot as plt
from scipy.ndimage import zoom
from simpa.io_handling import load_data_field
from simpa.core.simulation import simulate
from simpa.utils import Tags, Settings, TISSUE_LIBRARY
from simpa.simulation_components import OpticalForwardModelMcxAdapter, VolumeCreationModelModelBasedAdapter, \
    GaussianNoiseProcessingComponent
from simpa.processing.iterative_qPAI_algorithm import IterativeqPAIProcessingComponent
from simpa.core.device_digital_twins import RSOMExplorerP50


class TestqPAIReconstruction:
    """
    This class applies the iterative qPAI reconstruction algorithm on a simple test volume and
    - by visualizing the results - lets the user evaluate if the reconstruction is performed correctly.
    This test reconstruction contains a volume creation and an optical simulation.
    """

    def setUp(self):
        """
        Runs a pipeline consisting of volume creation and optical simulation. The resulting hdf5 file of the
        simple test volume is saved at SAVE_PATH location defined in the path_config.env file.
        """

        self.path_manager = PathManager()

        self.VOLUME_TRANSDUCER_DIM_IN_MM = 20
        self.VOLUME_PLANAR_DIM_IN_MM = 20
        self.VOLUME_HEIGHT_IN_MM = 20
        self.SPACING = 0.2
        self.RANDOM_SEED = 111
        self.VOLUME_NAME = "TestqPAIReconstructionVolume_" + str(self.RANDOM_SEED)

        np.random.seed(self.RANDOM_SEED)

        # These parameters set the general properties of the simulated volume
        self.general_settings = {
            Tags.RANDOM_SEED: self.RANDOM_SEED,
            Tags.VOLUME_NAME: self.VOLUME_NAME,
            Tags.SIMULATION_PATH: self.path_manager.get_hdf5_file_save_path(),
            Tags.SPACING_MM: self.SPACING,
            Tags.DIM_VOLUME_Z_MM: self.VOLUME_HEIGHT_IN_MM,
            Tags.DIM_VOLUME_X_MM: self.VOLUME_TRANSDUCER_DIM_IN_MM,
            Tags.DIM_VOLUME_Y_MM: self.VOLUME_PLANAR_DIM_IN_MM,
            Tags.WAVELENGTHS: [700]
        }
        self.settings = Settings(self.general_settings)

        self.settings.set_volume_creation_settings({
            Tags.SIMULATE_DEFORMED_LAYERS: True,
            Tags.STRUCTURES: self.create_example_tissue()
        })
        self.settings.set_optical_settings({
            Tags.OPTICAL_MODEL_NUMBER_PHOTONS: 1e7,
            Tags.OPTICAL_MODEL_BINARY_PATH: self.path_manager.get_mcx_binary_path(),
            Tags.OPTICAL_MODEL: Tags.OPTICAL_MODEL_MCX,
            Tags.ILLUMINATION_TYPE: Tags.ILLUMINATION_TYPE_PENCIL,
            Tags.LASER_PULSE_ENERGY_IN_MILLIJOULE: 50
        })
        self.settings["noise_model"] = {
            Tags.NOISE_MEAN: 0.0,
            Tags.NOISE_STD: 0.4,
            Tags.NOISE_MODE: Tags.NOISE_MODE_ADDITIVE,
            Tags.DATA_FIELD: Tags.OPTICAL_MODEL_INITIAL_PRESSURE,
            Tags.NOISE_NON_NEGATIVITY_CONSTRAINT: True
        }

        self.device = RSOMExplorerP50(element_spacing_mm=1.0)

        # run pipeline including volume creation and optical mcx simulation
        pipeline = [
            VolumeCreationModelModelBasedAdapter(self.settings),
            OpticalForwardModelMcxAdapter(self.settings),
            GaussianNoiseProcessingComponent(self.settings, "noise_model")
        ]
        simulate(pipeline, self.settings, self.device)

    def test_qpai_reconstruction(self):
        """
        Runs iterative qPAI reconstruction on test volume by accessing the settings dictionaries in a hdf5 file.
        """

        # set component settings of the iterative method
        # if tags are not defined the default is chosen for reconstruction
        component_settings = {
            Tags.DOWNSCALE_FACTOR: 0.76,
            Tags.ITERATIVE_RECONSTRUCTION_CONSTANT_REGULARIZATION: False,
            Tags.ITERATIVE_RECONSTRUCTION_MAX_ITERATION_NUMBER: 10,
            # for testing, we are interested in all intermediate absorption updates
            Tags.ITERATIVE_RECONSTRUCTION_SAVE_INTERMEDIATE_RESULTS: True,
            Tags.ITERATIVE_RECONSTRUCTION_STOPPING_LEVEL: 1e-5
        }

        self.settings["iterative_qpai_reconstruction"] = component_settings

        self.wavelength = self.settings[Tags.WAVELENGTH]
        absorption_gt = load_data_field(self.settings[Tags.SIMPA_OUTPUT_PATH], Tags.PROPERTY_ABSORPTION_PER_CM,
                                        self.wavelength)

        # if the initial pressure is resampled the ground truth has to be resampled to allow for comparison
        if Tags.DOWNSCALE_FACTOR in component_settings:
            self.absorption_gt = zoom(absorption_gt, component_settings[Tags.DOWNSCALE_FACTOR],
                                      order=1, mode="nearest")
        else:
            self.absorption_gt = zoom(absorption_gt, 0.73, order=1, mode="nearest")  # the default scale is 0.73

        # run the qPAI reconstruction
        IterativeqPAIProcessingComponent(self.settings, "iterative_qpai_reconstruction").run(self.device)

        # get last iteration result (3-d)
        hdf5_path = self.path_manager.get_hdf5_file_save_path() + "/" + self.VOLUME_NAME + ".hdf5"
        self.reconstructed_absorption = load_data_field(hdf5_path, Tags.ITERATIVE_qPAI_RESULT, self.wavelength)

        # get reconstructed absorptions (2-d middle slices) at each iteration step
        list_reconstructions_result_path = self.path_manager.get_hdf5_file_save_path() + \
                        "/List_reconstructed_qpai_absorptions_" + str(self.wavelength) + "_" + self.VOLUME_NAME + ".npy"
        self.list_2d_reconstructed_absorptions = np.load(list_reconstructions_result_path)

        # clean up files after test
        os.remove(hdf5_path)
        os.remove(list_reconstructions_result_path)

    def visualize_qpai_test_results(self):
        """
        Performs visualization of reconstruction results to allow for evaluation.
        The resulting figure displays the ground truth absorption coefficients, the corresponding reconstruction
        results and the difference between both for the middle plane in y-z and x-z direction, as well as the
        reconstruction results at each iteration step in x-z direction. The number of iteration should be larger
        than four to enable visualization.
        """

        # compute absolute differences
        difference_absorption = self.absorption_gt - self.reconstructed_absorption

        if np.min(self.absorption_gt) > np.min(self.reconstructed_absorption):
            cmin = np.min(self.reconstructed_absorption)
        else:
            cmin = np.min(self.absorption_gt)

        if np.max(self.absorption_gt) > np.max(self.reconstructed_absorption):
            cmax = np.max(self.absorption_gt)
        else:
            cmax = np.max(self.reconstructed_absorption)

        x_pos = int(np.shape(self.absorption_gt)[0] / 2)
        y_pos = int(np.shape(self.absorption_gt)[1] / 2)

        results_x_z = [self.absorption_gt[:, y_pos, :], self.reconstructed_absorption[:, y_pos, :],
                       difference_absorption[:, y_pos, :]]
        results_y_z = [self.absorption_gt[x_pos, :, :], self.reconstructed_absorption[x_pos, :, :],
                       difference_absorption[x_pos, :, :]]

        label = ["Absorption coefficients: ${\mu_a}^{gt}$", "Reconstruction: ${\mu_a}^{reconstr.}$",
             "Difference: ${\mu_a}^{gt} - {\mu_a}^{reconstr.}$"]

        plt.figure(figsize=(20, 15))
        plt.subplots_adjust(hspace=0.5, wspace=0.1)
        plt.suptitle("Iterative qPAI Reconstruction")

        for i, quantity in enumerate(results_y_z):
            plt.subplot(4, int(np.ceil(len(self.list_2d_reconstructed_absorptions) / 2)), i + 1)
            if i == 0:
                plt.ylabel("y-z", fontsize=10)
            plt.imshow(np.rot90(quantity, -1))
            plt.title(label[i], fontsize=10)
            plt.xticks(fontsize=6)
            plt.yticks(fontsize=6)
            plt.colorbar()
            if i != 2:
                plt.clim(cmin, cmax)
            else:
                plt.clim(np.min(difference_absorption), np.max(difference_absorption))

        for i, quantity in enumerate(results_x_z):
            plt.subplot(4, int(np.ceil(len(self.list_2d_reconstructed_absorptions) / 2)),
                        i + int(np.ceil(len(self.list_2d_reconstructed_absorptions) / 2)) + 1)
            if i == 0:
                plt.ylabel("x-z", fontsize=10)
            plt.imshow(np.rot90(quantity, -1))
            plt.title(label[i], fontsize=10)
            plt.xticks(fontsize=6)
            plt.yticks(fontsize=6)
            plt.colorbar()
            if i != 2:
                plt.clim(cmin, cmax)
            else:
                plt.clim(np.min(difference_absorption), np.max(difference_absorption))

        for i, quantity in enumerate(self.list_2d_reconstructed_absorptions):
            plt.subplot(4, int(np.ceil(len(self.list_2d_reconstructed_absorptions) / 2)),
                        i + 2 * int(np.ceil(len(self.list_2d_reconstructed_absorptions) / 2)) + 1)
            plt.title("Iteration step: " + str(i + 1), fontsize=8)
            plt.imshow(np.rot90(quantity, -1))  # absorption maps in list are already 2-d
            plt.colorbar()
            plt.clim(cmin, cmax)
            plt.axis('off')

        plt.show()
        plt.close()

    def create_example_tissue(self):
        """
        This is a very simple example script of how to create a tissue definition.
        It contains a muscular background, an epidermis layer on top of the muscles
        and two blood vessels. It is used for volume creation.
        """
        background_dictionary = Settings()
        background_dictionary[Tags.MOLECULE_COMPOSITION] = TISSUE_LIBRARY.muscle()
        background_dictionary[Tags.STRUCTURE_TYPE] = Tags.BACKGROUND

        epidermis_structure = Settings()
        epidermis_structure[Tags.PRIORITY] = 1
        epidermis_structure[Tags.STRUCTURE_START_MM] = [0, 0, 2]
        epidermis_structure[Tags.STRUCTURE_END_MM] = [0, 0, 2.5]
        epidermis_structure[Tags.MOLECULE_COMPOSITION] = TISSUE_LIBRARY.epidermis()
        epidermis_structure[Tags.CONSIDER_PARTIAL_VOLUME] = True
        epidermis_structure[Tags.ADHERE_TO_DEFORMATION] = True
        epidermis_structure[Tags.STRUCTURE_TYPE] = Tags.HORIZONTAL_LAYER_STRUCTURE

        vessel_structure_1 = Settings()
        vessel_structure_1[Tags.PRIORITY] = 2
        vessel_structure_1[Tags.STRUCTURE_START_MM] = [self.VOLUME_TRANSDUCER_DIM_IN_MM / 2.5, 0,
                                                       self.VOLUME_HEIGHT_IN_MM / 2]
        vessel_structure_1[Tags.STRUCTURE_END_MM] = [self.VOLUME_TRANSDUCER_DIM_IN_MM / 2.5,
                                                     self.VOLUME_PLANAR_DIM_IN_MM, self.VOLUME_HEIGHT_IN_MM / 2]
        vessel_structure_1[Tags.STRUCTURE_RADIUS_MM] = 1.75
        vessel_structure_1[Tags.STRUCTURE_ECCENTRICITY] = 0.85
        vessel_structure_1[Tags.MOLECULE_COMPOSITION] = TISSUE_LIBRARY.blood(1.0)
        vessel_structure_1[Tags.CONSIDER_PARTIAL_VOLUME] = True
        vessel_structure_1[Tags.ADHERE_TO_DEFORMATION] = True
        vessel_structure_1[Tags.STRUCTURE_TYPE] = Tags.ELLIPTICAL_TUBULAR_STRUCTURE

        vessel_structure_2= Settings()
        vessel_structure_2[Tags.PRIORITY] = 3
        vessel_structure_2[Tags.STRUCTURE_START_MM] = [self.VOLUME_TRANSDUCER_DIM_IN_MM / 2, 0,
                                                       self.VOLUME_HEIGHT_IN_MM / 3]
        vessel_structure_2[Tags.STRUCTURE_END_MM] = [self.VOLUME_TRANSDUCER_DIM_IN_MM / 2,
                                                     self.VOLUME_PLANAR_DIM_IN_MM, self.VOLUME_HEIGHT_IN_MM / 3]
        vessel_structure_2[Tags.STRUCTURE_RADIUS_MM] = 0.75
        vessel_structure_2[Tags.MOLECULE_COMPOSITION] = TISSUE_LIBRARY.blood(0.5)
        vessel_structure_2[Tags.CONSIDER_PARTIAL_VOLUME] = True
        vessel_structure_2[Tags.STRUCTURE_TYPE] = Tags.CIRCULAR_TUBULAR_STRUCTURE

        tissue_dict = Settings()
        tissue_dict[Tags.BACKGROUND] = background_dictionary
        tissue_dict["epidermis"] = epidermis_structure
        tissue_dict["vessel_1"] = vessel_structure_1
        tissue_dict["vessel_2"] = vessel_structure_2

        return tissue_dict


if __name__ == '__main__':
    test = TestqPAIReconstruction()
    test.setUp()
    test.test_qpai_reconstruction()
    test.visualize_qpai_test_results()
