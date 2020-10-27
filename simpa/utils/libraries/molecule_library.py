# The MIT License (MIT)
#
# Copyright (c) 2018 Computer Assisted Medical Interventions Group, DKFZ
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

import numpy as np
from simpa.utils import Tags
from simpa.utils.tissue_properties import TissueProperties
from simpa.utils.libraries.literature_values import OpticalTissueProperties
from simpa.utils import AbsorptionSpectrum
from simpa.utils import SPECTRAL_LIBRARY
from simpa.utils.calculate import calculate_oxygenation


class MolecularComposition(list):

    def __init__(self, segmentation_type=None, molecular_composition_settings=None):
        super().__init__()
        self.segmentation_type = segmentation_type
        self.internal_properties = TissueProperties()
        self.cached_absorption = np.ones((5000, )) * -1
        self.cached_scattering = np.ones((5000,)) * -1

        if molecular_composition_settings is None:
            return

        _keys = molecular_composition_settings.keys()
        for molecule_name in _keys:
            self.append(molecular_composition_settings[molecule_name])

    def update_internal_properties(self):
        """
        FIXME
        """
        self.internal_properties = TissueProperties()
        self.internal_properties[Tags.PROPERTY_SEGMENTATION] = self.segmentation_type
        self.internal_properties[Tags.PROPERTY_OXYGENATION] = calculate_oxygenation(self)
        for molecule in self:
            self.internal_properties.volume_fraction += molecule.volume_fraction
            self.internal_properties[Tags.PROPERTY_ANISOTROPY] += molecule.volume_fraction * molecule.anisotropy
            self.internal_properties[Tags.PROPERTY_GRUNEISEN_PARAMETER] += molecule.volume_fraction * molecule.gruneisen_parameter
            self.internal_properties[Tags.PROPERTY_DENSITY] += molecule.volume_fraction * molecule.density
            self.internal_properties[Tags.PROPERTY_SPEED_OF_SOUND] += molecule.volume_fraction * molecule.speed_of_sound
            self.internal_properties[Tags.PROPERTY_ALPHA_COEFF] += molecule.volume_fraction * molecule.alpha_coefficient

        if self.internal_properties.volume_fraction > 1:
            self.internal_properties[Tags.PROPERTY_ANISOTROPY] /= self.internal_properties.volume_fraction

    def get_properties_for_wavelength(self, wavelength) -> TissueProperties:
        if self.cached_absorption[wavelength] != -1:
            self.internal_properties[Tags.PROPERTY_ABSORPTION_PER_CM] = self.cached_absorption[wavelength]
            self.internal_properties[Tags.PROPERTY_SCATTERING_PER_CM] = self.cached_scattering[wavelength]
        else:
            self.internal_properties[Tags.PROPERTY_ABSORPTION_PER_CM] = 0
            self.internal_properties[Tags.PROPERTY_SCATTERING_PER_CM] = 0
            for molecule in self:
                self.internal_properties[Tags.PROPERTY_ABSORPTION_PER_CM] += (molecule.volume_fraction *
                                                                              molecule.spectrum.get_absorption_for_wavelength(wavelength))
                self.internal_properties[Tags.PROPERTY_SCATTERING_PER_CM] += (molecule.volume_fraction * (molecule.mus500 * (molecule.f_ray *
                                                                              (wavelength / 500) ** 1e-4 + (1 - molecule.f_ray) *
                                                                              (wavelength / 500) ** -molecule.b_mie)))
            self.cached_absorption[wavelength] = self.internal_properties[Tags.PROPERTY_ABSORPTION_PER_CM]
            self.cached_scattering[wavelength] = self.internal_properties[Tags.PROPERTY_SCATTERING_PER_CM]
        return self.internal_properties


class Molecule(object):

    def __init__(self, spectrum: AbsorptionSpectrum = None,
                 volume_fraction: float = None,
                 mus500: float = None, f_ray: float = None, b_mie: float = None,
                 anisotropy: float = None, gruneisen_parameter: float = None,
                 density: float = None, speed_of_sound: float = None,
                 alpha_coefficient: float = None):
        """
        :param spectrum: AbsorptionSpectrum
        :param volume_fraction: float
        :param mus500: float The scattering coefficient at 500 nanometers
        :param f_ray: float
        :param b_mie: float
        :param anisotropy: float
        """
        if spectrum is None:
            spectrum = SPECTRAL_LIBRARY.CONSTANT_ABSORBER_ZERO
        if not isinstance(spectrum, AbsorptionSpectrum):
            raise TypeError("The given spectrum was not of type AbsorptionSpectrum!")
        self.spectrum = spectrum

        if volume_fraction is None:
            volume_fraction = 0.0
        if not isinstance(volume_fraction, float):
            raise TypeError("The given volume_fraction was not of type float!")
        self.volume_fraction = volume_fraction

        if mus500 is None:
            mus500 = 1e-20
        if not isinstance(mus500, float):
            raise TypeError("The given mus500 was not of type float!")
        self.mus500 = mus500

        if f_ray is None:
            f_ray = 0.0
        if not isinstance(f_ray, float):
            raise TypeError("The given f_ray was not of type float!")
        self.f_ray = f_ray

        if b_mie is None:
            b_mie = 0.0
        if not isinstance(b_mie, float):
            raise TypeError("The given b_mie was not of type float!")
        self.b_mie = b_mie

        if anisotropy is None:
            anisotropy = 0.0
        if not isinstance(anisotropy, float):
            raise TypeError("The given anisotropy was not of type float!")
        self.anisotropy = anisotropy

        if gruneisen_parameter is None:
            gruneisen_parameter = 1.0
        if not isinstance(gruneisen_parameter, float):
            raise TypeError("The given gruneisen_parameter was not of type float!")
        self.gruneisen_parameter = gruneisen_parameter

        if density is None:
            density = 0.0
        if not isinstance(density, float):
            raise TypeError("The given density was not of type float!")
        self.density = density

        if speed_of_sound is None:
            speed_of_sound = 0.0
        if not isinstance(speed_of_sound, float):
            raise TypeError("The given speed_of_sound was not of type float!")
        self.speed_of_sound = speed_of_sound

        if alpha_coefficient is None:
            alpha_coefficient = 0.0
        if not isinstance(alpha_coefficient, float):
            raise TypeError("The given alpha_coefficient was not of type float!")
        self.alpha_coefficient = alpha_coefficient


class MoleculeLibrary(object):

    # Main absorbers
    def water(self, volume_fraction: float = 1.0):
        return Molecule(spectrum=SPECTRAL_LIBRARY.WATER,
                        volume_fraction=volume_fraction, mus500=0.0,
                        b_mie=0.0, f_ray=0.0, anisotropy=1.0)

    def oxyhemoglobin(self, volume_fraction: float = 1.0):
        return Molecule(
            spectrum=SPECTRAL_LIBRARY.OXYHEMOGLOBIN,
            volume_fraction=volume_fraction,
            mus500=OpticalTissueProperties.MUS500_BLOOD,
            b_mie=OpticalTissueProperties.BMIE_BLOOD,
            f_ray=OpticalTissueProperties.FRAY_BLOOD,
            anisotropy=OpticalTissueProperties.STANDARD_ANISOTROPY
        )

    def deoxyhemoglobin(self, volume_fraction: float = 1.0):
        return Molecule(
            spectrum=SPECTRAL_LIBRARY.DEOXYHEMOGLOBIN,
            volume_fraction=volume_fraction,
            mus500=OpticalTissueProperties.MUS500_BLOOD,
            b_mie=OpticalTissueProperties.BMIE_BLOOD,
            f_ray=OpticalTissueProperties.FRAY_BLOOD,
            anisotropy=OpticalTissueProperties.STANDARD_ANISOTROPY
        )

    def melanin(self, volume_fraction: float = 1.0):
        return Molecule(
            spectrum=SPECTRAL_LIBRARY.MELANIN,
            volume_fraction=volume_fraction,
            mus500=OpticalTissueProperties.MUS500_EPIDERMIS,
            b_mie=OpticalTissueProperties.BMIE_EPIDERMIS,
            f_ray=OpticalTissueProperties.FRAY_EPIDERMIS,
            anisotropy=OpticalTissueProperties.STANDARD_ANISOTROPY
        )

    def fat(self, volume_fraction: float = 1.0):
        return Molecule(
            spectrum=SPECTRAL_LIBRARY.FAT,
            volume_fraction=volume_fraction,
            mus500=OpticalTissueProperties.MUS500_FAT,
            b_mie=OpticalTissueProperties.BMIE_FAT,
            f_ray=OpticalTissueProperties.FRAY_FAT,
            anisotropy=OpticalTissueProperties.STANDARD_ANISOTROPY
        )

    # Scatterers
    def constant_scatterer(self, scattering_coefficient: float = 100.0, anisotropy: float = 0.9,
                           volume_fraction: float = 1.0):
        return Molecule(spectrum=SPECTRAL_LIBRARY.CONSTANT_ABSORBER_ZERO,
                        volume_fraction=volume_fraction, mus500=scattering_coefficient,
                        b_mie=0.0, f_ray=0.0, anisotropy=anisotropy)

    def soft_tissue_scatterer(self, volume_fraction: float = 1.0):
        return Molecule(spectrum=SPECTRAL_LIBRARY.CONSTANT_ABSORBER_ZERO,
                        volume_fraction=volume_fraction,
                        mus500=OpticalTissueProperties.MUS500_BACKGROUND_TISSUE,
                        b_mie=OpticalTissueProperties.BMIE_BACKGROUND_TISSUE,
                        f_ray=OpticalTissueProperties.FRAY_BACKGROUND_TISSUE,
                        anisotropy=OpticalTissueProperties.STANDARD_ANISOTROPY)

    def epidermal_scatterer(self, volume_fraction: float = 1.0):
        return Molecule(spectrum=SPECTRAL_LIBRARY.CONSTANT_ABSORBER_ZERO,
                        volume_fraction=volume_fraction,
                        mus500=OpticalTissueProperties.MUS500_EPIDERMIS,
                        b_mie=OpticalTissueProperties.BMIE_EPIDERMIS,
                        f_ray=OpticalTissueProperties.FRAY_EPIDERMIS,
                        anisotropy=OpticalTissueProperties.STANDARD_ANISOTROPY)

    def dermal_scatterer(self, volume_fraction: float = 1.0):
        return Molecule(spectrum=SPECTRAL_LIBRARY.CONSTANT_ABSORBER_ZERO,
                        volume_fraction=volume_fraction,
                        mus500=OpticalTissueProperties.MUS500_DERMIS,
                        b_mie=OpticalTissueProperties.BMIE_DERMIS,
                        f_ray=OpticalTissueProperties.FRAY_DERMIS,
                        anisotropy=OpticalTissueProperties.STANDARD_ANISOTROPY)

    def bone_scatterer(self, volume_fraction: float = 1.0):
        return Molecule(
            spectrum=SPECTRAL_LIBRARY.CONSTANT_ABSORBER_ZERO,
            volume_fraction=volume_fraction,
            mus500=OpticalTissueProperties.MUS500_BONE,
            b_mie=OpticalTissueProperties.BMIE_BONE,
            f_ray=OpticalTissueProperties.FRAY_BONE,
            anisotropy=OpticalTissueProperties.STANDARD_ANISOTROPY
        )


MOLECULE_LIBRARY = MoleculeLibrary()
