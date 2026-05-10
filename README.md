# PennAnomaloscope

This site provides info on building the Penn Anomaloscope, an Arduino-based LED anomaloscope designed for teaching and (maybe) research.

The anomaloscope was developed by Leana Keesing and David Brainard, with support from Optica.  This site began as a fork of Leana Keesing's original site, and includes code that was originally provided as part of the Brainard Lab's Teaching Code repository. This is now the respository that (as of 2025) is being developed and maintained.

If you use the Penn Anomaloscope in a publication, please cite as:

Keesing, L. & Brainard, D. H. (2022). The Penn anomaloscope, https://github.com/BrainardLab/PennAnomaloscope. 

## Reports that use the Penn Anomaloscope

Turner, D., Keesing, L. Gray, J., Morimoto, T. McClements, M. MacLaren, R. Hexley, A., Brainard, D. H., Smithson, H. E. (2024). Testing the reliability and validity of Rayleigh matches and heterochromatic flicker photometry settings on an Arduino-based LED device. Abstract presented at the 2024 27th Meeting of the International Colour Vision Society, Ljubljana, Slovenia, July 5-9, 2024.

Ling, L., E. Bilgiç, M. Mak, H. H. Smith, N. Strukov, J. D. Mollon, Danilova, M. V. (2025). Assessment of the Penn anomaloscope. Biomedical Optics Express 16(10). https://opg.optica.org/boe/fulltext.cfm?uri=boe-16-10-3978&id=576497.

## CAD

3D printing STL files for the housing.  The README has a link to a movie that shows the electronics being assembled into the 3D printed housing parts.

## Code

Some basic code for controlling the anomaloscope. Includes code contributed by others. See ICVS2025 directory for code and calibration data used at the ICVS 2025 Summer School.  See Code/xContributed for code contributed by others.

## Electronics

Parts list for the electronics (see 2025 updated and 2026 UK versions) as well as instructions for assembling the electronics.

## xContributed

Contributions that are not software (see Code/xContributed for contributed software).

- 2026-05-10 - PennFilerTesting.pptx from Dana Turner.  This reporst on spectral measurements of various LED/filter combinations with the goal of finding combinations that lead to more balanced R and G values at typical matches, and thus avoiding quantization issues with the original parts.

## Updates

- 02-2025 - Uploaded updated parts list provided by Alexander Gokan.
- 02-2025 - Assembly instructions expanded and made consistent with how we are now building these.
- 08-2025 - Add ICVS2025 materials in their own directory.
- 09-2025 - Add link to Ling et al. paper.
- 10-2025 - Add python and arduino direct code provided by Alexander Gokan.
- 05-2026 - Add UK parts list provided by Dana Turner (in Electronics)
