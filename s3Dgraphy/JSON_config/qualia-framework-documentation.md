# Extended Matrix Qualia Framework Documentation 

## Overview
The Extended Matrix Qualia Framework provides a comprehensive structure for describing and managing qualitative properties of cultural heritage objects within the Extended Matrix methodology. This framework consists of three interconnected components:
- Qualia definitions and categories
- Document types specifications
- Extractor types specifications

## Framework Structure

### 1. Qualia Categories
The framework defines five main families of qualia, each addressing different aspects of cultural heritage objects:

#### 1.1 Physical/Material Qualia
Properties describing tangible and measurable characteristics.

**Dimensional Qualia**
- **Height**
  - Getty AAT: 300055644
  - CIDOC CRM: E54_Dimension
  - Dublin Core: format.extent
  - Units: cm, m, ft
  - Expected extractors: direct measurement, 3D model measurement, drawing measurement
- **Width**
  - Getty AAT: 300055647
  - CIDOC CRM: E54_Dimension
  - Dublin Core: format.extent
  - Units: cm, m, ft
  - Expected extractors: direct measurement, 3D model measurement, drawing measurement
- **Depth**
  - Getty AAT: 300072633
  - CIDOC CRM: E54_Dimension
  - Dublin Core: format.extent
  - Units: cm, m, ft
  - Expected extractors: direct measurement, 3D model measurement, drawing measurement
- **Weight**
  - Getty AAT: 300056240
  - CIDOC CRM: E54_Dimension
  - Units: kg, g, lb
  - Expected extractors: direct measurement
- **Diameter**
  - Getty AAT: 300055624
  - CIDOC CRM: E54_Dimension
  - Dublin Core: format.extent
  - Units: cm, m, ft
  - Expected extractors: direct measurement, 3D model measurement, drawing measurement

**Material Qualia**
- **Material Type**
  - Getty AAT: 300010357
  - CIDOC CRM: E57_Material
  - Dublin Core: format.medium
  - Vocabulary source: Getty AAT
  - Expected extractors: visual inspection, laboratory analysis
- **Origin Type**
  - Values: natural, artificial
  - Data type: controlled vocabulary
- **Surface Treatment**
  - Getty AAT: 300053895
  - CIDOC CRM: E11_Modification
  - Dublin Core: description
  - Expected extractors: visual inspection, surface analysis
- **Granulometry**
  - Getty AAT: 300417183
  - CIDOC CRM: E54_Dimension
  - Values: fine, medium, coarse
  - Expected extractors: visual inspection, microscopic analysis

**Conservation Qualia**
- **Conservation State**
  - Getty AAT: 300015332
  - CIDOC CRM: E3_Condition_State
  - ICOM CIDOC: Object Condition Information
  - Values: excellent, good, fair, poor, very_poor
  - Expected extractors: visual inspection, condition assessment
- **Integrity**
  - Getty AAT: 300388714
  - CIDOC CRM: E3_Condition_State
  - Dublin Core: description
  - Data type: percentage (0-100)
  - Expected extractors: visual inspection, 3D model analysis

**Technical Qualia**
- **Construction Technique**
  - Getty AAT: 300000022
  - CIDOC CRM: E29_Design_or_Procedure
  - Dublin Core: description
  - Vocabulary source: Getty AAT
  - Expected extractors: visual inspection, technical analysis

#### 1.2 Spatiotemporal Qualia
Properties related to space and time placement.

**Spatial Qualia**
- **Absolute Position**
  - Getty AAT: 300387565
  - CIDOC CRM: E53_Place
  - Coordinate system: cartesian_3d (x, y, z)
  - Reference system: WGS84
  - Expected extractors: GPS survey, total station survey, 3D model measurement
- **Orientation**
  - Getty AAT: 300131574
  - CIDOC CRM: E54_Dimension
  - Components: azimuth, tilt, roll
  - Units: degrees
  - Expected extractors: compass measurement, 3D model analysis
- **Elevation**
  - Getty AAT: 300447457
  - CIDOC CRM: E54_Dimension
  - Units: m, ft
  - Expected extractors: GPS survey, total station survey, leveling
- **Arrangement**
  - Getty AAT: 300067654
  - CIDOC CRM: E55_Type
  - Values: linear, radial, grid, clustered, scattered, concentric
  - Expected extractors: visual inspection, spatial analysis

**Temporal Qualia**
- **Absolute Start/End Date**
  - Getty AAT: 300404284
  - CIDOC CRM: E52_Time-Span
  - Format: YYYY-MM-DD
- **Dating Method**
  - Getty AAT: 300054714
  - CIDOC CRM: E55_Type
  - Values: stratigraphy, typology, c14, dendrochronology, historical_sources, stylistic_analysis
  - Expected extractors: dating analysis, laboratory analysis

#### 1.3 Functional Qualia
Use and performance characteristics.

**Telic Qualia**
- **Primary Function**
  - Getty AAT: 300068003
  - CIDOC CRM: E55_Type
  - Vocabulary source: Getty AAT
  - Expected extractors: functional analysis, historical research, comparative analysis
- **Secondary Functions**
  - Getty AAT: 300068003
  - CIDOC CRM: E55_Type
  - Vocabulary source: Getty AAT
  - Expected extractors: functional analysis, historical research

**Structural Qualia**
- **Structural Role**
  - Getty AAT: 300264518
  - CIDOC CRM: E55_Type
  - Values: load_bearing, non_load_bearing, reinforcing, connecting, supporting, decorative
  - Expected extractors: structural analysis, architectural analysis
- **Stress Type**
  - Getty AAT: 300264519
  - CIDOC CRM: E55_Type
  - Values: compression, tension, bending, shear, torsion
  - Expected extractors: structural analysis

**Performative Qualia**
- **Load Capacity**
  - Getty AAT: 300265725
  - CIDOC CRM: E54_Dimension
  - Units: kN, kgf
  - Expected extractors: structural analysis, load testing

#### 1.4 Cultural/Interpretive Qualia
Cultural significance and meaning.

**Stylistic Qualia**
- **Artistic Style**
  - Getty AAT: 300015646
  - CIDOC CRM: E55_Type
  - Vocabulary source: Getty AAT
  - Expected extractors: style analysis, comparative analysis
- **Stylistic Influences**
  - Getty AAT: 300015646
  - CIDOC CRM: E55_Type
  - Vocabulary source: Getty AAT
  - Expected extractors: historical analysis, stylistic analysis

#### 1.5 Contextual Qualia
Management and administrative information (Experimental category).

**Administrative Qualia**
- **Inventory Number**
  - Getty AAT: 300312355
  - CIDOC CRM: P48_has_preferred_identifier
  - Expected extractors: archival research, museum documentation
- **Legal Status**
  - Getty AAT: 300435427
  - CIDOC CRM: P104_is_subject_to
  - Vocabulary source: Getty AAT
  - Expected extractors: legal documentation, administrative research
- **Intervention History**
  - Getty AAT: 300379504
  - CIDOC CRM: E11_Modification
- **Conservation Status**
  - Getty AAT: 300435429
  - CIDOC CRM: P44_has_condition
  - Vocabulary source: Getty AAT
  - Expected extractors: conservation assessment, condition survey
- **Access Conditions**
  - Getty AAT: 300435430
  - CIDOC CRM: P104_is_subject_to
  - Vocabulary source: Getty AAT
  - Expected extractors: access assessment, management review

### 2. Supporting Components

#### 2.1 Document Types

##### 2.1.1 Spatial Documentation
Vocabulary Mappings:
- Getty AAT: 300389935
- CIDOC CRM: E36_Visual_Item (P67_refers_to)
- Dublin Core: dcterms:spatial

###### 3D Model
- Formats: gltf, obj, ply, fbx, 3ds, e57
- Possible Extractions:
  - Dimensions
  - Spatial relationships
  - Geometric features
  - Volume
  - Surface properties
- Supported Extractors:
  - 3D model analysis
  - Geometric analysis
  - Spatial pattern analysis
- Metadata Requirements:
  - Mandatory:
    - Creation date
    - Creator
    - Software used
    - Coordinate system
    - Spatial resolution
  - Optional:
    - Accuracy assessment
    - Processing workflow
    - Registration method
    - Point cloud density

###### Technical Drawing
- Formats: dwg, dxf, pdf, svg
- Possible Extractions:
  - Dimensions
  - Construction details
  - Spatial layout
  - Architectural elements
- Supported Extractors:
  - Technical drawing analysis
  - Architectural analysis
- Metadata Requirements:
  - Mandatory:
    - Creation date
    - Author
    - Scale
    - Drawing type
    - Reference system
  - Optional:
    - Revision history
    - Drawing conventions
    - Associated specifications

##### 2.1.2 Scientific Documentation
Vocabulary Mappings:
- Getty AAT: 300379612
- CIDOC CRM: E31_Document (P140_assigned_attribute_to)

###### Material Analysis Report
- Formats: pdf, docx, xlsx
- Possible Extractions:
  - Material composition
  - Physical properties
  - Chemical properties
  - Degradation patterns
- Supported Extractors:
  - Lab report analysis
  - Material composition analysis
- Metadata Requirements:
  - Mandatory:
    - Analysis date
    - Laboratory
    - Analysis method
    - Sampling strategy
    - Analyst
  - Optional:
    - Equipment used
    - Calibration data
    - Error margins

###### Dating Analysis Report
- Formats: pdf, docx, xlsx
- Possible Extractions:
  - Absolute date
  - Date range
  - Dating method reliability
  - Chronological context
- Supported Extractors:
  - Scientific dating analysis
  - Chronological analysis
- Metadata Requirements:
  - Mandatory:
    - Analysis date
    - Laboratory
    - Dating method
    - Sample description
    - Calibration curve
  - Optional:
    - Sample preparation
    - Contamination assessment
    - Comparative samples

##### 2.1.3 Historical Documentation
Vocabulary Mappings:
- Getty AAT: 300343082
- CIDOC CRM: E31_Document (P70_documents)
- Dublin Core: dcterms:source

###### Archival Document
- Formats: pdf, txt, docx, tiff
- Possible Extractions:
  - Historical context
  - Construction history
  - Ownership history
  - Modification events
- Supported Extractors:
  - Archival document analysis
  - Historical context analysis
- Metadata Requirements:
  - Mandatory:
    - Archive reference
    - Document date
    - Document type
    - Archival location
  - Optional:
    - Transcription details
    - Preservation state
    - Access restrictions

###### Historical Photograph
- Formats: tiff, jpg, pdf
- Possible Extractions:
  - Historical appearance
  - Temporal changes
  - Architectural features
  - Urban context
- Supported Extractors:
  - Photographic analysis
  - Temporal change analysis
- Metadata Requirements:
  - Mandatory:
    - Photo date
    - Photographer
    - Archive reference
    - Subject location
  - Optional:
    - Camera details
    - Print type
    - Negative reference

##### 2.1.4 Conservation Documentation
Vocabulary Mappings:
- Getty AAT: 300379612
- CIDOC CRM: E31_Document (P140_assigned_attribute_to)
- Dublin Core: dcterms:provenance

###### Condition Report
- Formats: pdf, docx, xlsx
- Possible Extractions:
  - Conservation state
  - Degradation patterns
  - Risk factors
  - Intervention priorities
- Supported Extractors:
  - Condition report analysis
  - Conservation assessment
- Metadata Requirements:
  - Mandatory:
    - Assessment date
    - Assessor
    - Assessment method
    - Condition classification
  - Optional:
    - Environmental data
    - Previous treatments
    - Monitoring history

###### Intervention Report
- Formats: pdf, docx, xlsx
- Possible Extractions:
  - Treatment methods
  - Materials used
  - Intervention results
  - Follow-up recommendations
- Supported Extractors:
  - Intervention history analysis
  - Treatment effectiveness analysis
- Metadata Requirements:
  - Mandatory:
    - Intervention date
    - Conservator
    - Intervention type
    - Materials used
    - Documentation method
  - Optional:
    - Preliminary tests
    - Environmental conditions
    - Post-treatment monitoring

#### 2.2 Document Types

##### 2.2.1 Spatial Documentation
Vocabulary Mappings:
- Getty AAT: 300389935
- CIDOC CRM: E36_Visual_Item (P67_refers_to)
- Dublin Core: dcterms:spatial

###### 3D Model
- Formats: gltf, obj, ply, fbx, 3ds, e57
- Possible Extractions:
  - Dimensions
  - Spatial relationships
  - Geometric features
  - Volume
  - Surface properties
- Supported Extractors:
  - 3D model analysis
  - Geometric analysis
  - Spatial pattern analysis
- Metadata Requirements:
  - Mandatory:
    - Creation date
    - Creator
    - Software used
    - Coordinate system
    - Spatial resolution
  - Optional:
    - Accuracy assessment
    - Processing workflow
    - Registration method
    - Point cloud density

###### Technical Drawing
- Formats: dwg, dxf, pdf, svg
- Possible Extractions:
  - Dimensions
  - Construction details
  - Spatial layout
  - Architectural elements
- Supported Extractors:
  - Technical drawing analysis
  - Architectural analysis
- Metadata Requirements:
  - Mandatory:
    - Creation date
    - Author
    - Scale
    - Drawing type
    - Reference system
  - Optional:
    - Revision history
    - Drawing conventions
    - Associated specifications

##### 2.2.2 Scientific Documentation
Vocabulary Mappings:
- Getty AAT: 300379612
- CIDOC CRM: E31_Document (P140_assigned_attribute_to)

###### Material Analysis Report
- Formats: pdf, docx, xlsx
- Possible Extractions:
  - Material composition
  - Physical properties
  - Chemical properties
  - Degradation patterns
- Supported Extractors:
  - Lab report analysis
  - Material composition analysis
- Metadata Requirements:
  - Mandatory:
    - Analysis date
    - Laboratory
    - Analysis method
    - Sampling strategy
    - Analyst
  - Optional:
    - Equipment used
    - Calibration data
    - Error margins

###### Dating Analysis Report
- Formats: pdf, docx, xlsx
- Possible Extractions:
  - Absolute date
  - Date range
  - Dating method reliability
  - Chronological context
- Supported Extractors:
  - Scientific dating analysis
  - Chronological analysis
- Metadata Requirements:
  - Mandatory:
    - Analysis date
    - Laboratory
    - Dating method
    - Sample description
    - Calibration curve
  - Optional:
    - Sample preparation
    - Contamination assessment
    - Comparative samples

##### 2.2.3 Historical Documentation
Vocabulary Mappings:
- Getty AAT: 300343082
- CIDOC CRM: E31_Document (P70_documents)
- Dublin Core: dcterms:source

###### Archival Document
- Formats: pdf, txt, docx, tiff
- Possible Extractions:
  - Historical context
  - Construction history
  - Ownership history
  - Modification events
- Supported Extractors:
  - Archival document analysis
  - Historical context analysis
- Metadata Requirements:
  - Mandatory:
    - Archive reference
    - Document date
    - Document type
    - Archival location
  - Optional:
    - Transcription details
    - Preservation state
    - Access restrictions

###### Historical Photograph
- Formats: tiff, jpg, pdf
- Possible Extractions:
  - Historical appearance
  - Temporal changes
  - Architectural features
  - Urban context
- Supported Extractors:
  - Photographic analysis
  - Temporal change analysis
- Metadata Requirements:
  - Mandatory:
    - Photo date
    - Photographer
    - Archive reference
    - Subject location
  - Optional:
    - Camera details
    - Print type
    - Negative reference

##### 2.2.4 Conservation Documentation
Vocabulary Mappings:
- Getty AAT: 300379612
- CIDOC CRM: E31_Document (P140_assigned_attribute_to)
- Dublin Core: dcterms:provenance

###### Condition Report
- Formats: pdf, docx, xlsx
- Possible Extractions:
  - Conservation state
  - Degradation patterns
  - Risk factors
  - Intervention priorities
- Supported Extractors:
  - Condition report analysis
  - Conservation assessment
- Metadata Requirements:
  - Mandatory:
    - Assessment date
    - Assessor
    - Assessment method
    - Condition classification
  - Optional:
    - Environmental data
    - Previous treatments
    - Monitoring history

###### Intervention Report
- Formats: pdf, docx, xlsx
- Possible Extractions:
  - Treatment methods
  - Materials used
  - Intervention results
  - Follow-up recommendations
- Supported Extractors:
  - Intervention history analysis
  - Treatment effectiveness analysis
- Metadata Requirements:
  - Mandatory:
    - Intervention date
    - Conservator
    - Intervention type
    - Materials used
    - Documentation method
  - Optional:
    - Preliminary tests
    - Environmental conditions
    - Post-treatment monitoring

Each extractor type includes:
- Standard procedures
- Required expertise
- Quality control measures
- Documentation requirements
- Reliability assessment criteria

## Implementation Principles

### 1. Vocabulary Control
- Integration with standard vocabularies (Getty AAT, CIDOC CRM)
- Support for domain-specific terminology
- Hierarchical organization of terms

### 2. Property Structure
Each qualia property includes:
- Clear identification and description
- Standard vocabulary mappings
- Expected data types
- Possible extraction methods

### 3. Documentation Requirements
For each document type:
- Mandatory and optional metadata
- Supported formats
- Possible extractions

### 4. Quality Control
For each extractor type:
- Accuracy levels
- Reliability factors
- Documentation requirements

## Future Development

### 1. Validation System
Development needed for:
- Property type validation against vocabularies
- Document content validation
- Extractor method validation

### 2. Vocabulary Integration
Implementation required for:
- Getty AAT term resolution
- CIDOC CRM mapping
- Custom vocabulary management

### 3. Inter-relationships
Development of:
- Property-Document relationships
- Document-Extractor relationships
- Cross-property validations

## Usage in Extended Matrix

The framework supports:
1. Systematic description of cultural heritage objects
2. Documentation of interpretive processes
3. Management of temporal and cultural contexts
4. Integration with stratigraphic analysis

## Technical Implementation Notes

### 1. JSON Structure
The framework is implemented through three main JSON files:
- qualia-types.json: Property definitions
- document-types.json: Document specifications
- extractor-types.json: Extractor methods

### 2. Validation Requirements
Future implementation should include:
- JSON Schema validation
- Vocabulary term validation
- Relationship constraint checking

### 3. Integration Points
- S3DGraphy graph structure
- Extended Matrix methodology
- External vocabulary services

## Conclusion
This framework provides a foundation for systematic cultural heritage documentation while maintaining flexibility for domain-specific extensions and interpretations. Future development should focus on validation systems and vocabulary integration.