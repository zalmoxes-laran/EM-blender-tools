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
- **Dimensional**: Measurable spatial properties (height, width, depth, diameter)
- **Material**: Physical material properties (material type, composition, granulometry)
- **Conservation**: State of preservation and decay
- **Technical**: Construction and execution techniques

#### 1.2 Spatiotemporal Qualia
- **Positional**: Location and orientation in space
- **Chronological**: Dating and temporal placement
- **Stratigraphic**: Relationships with other units (managed through edges in the graph)

#### 1.3 Functional Qualia
- **Telic**: Original and intended functions
- **Structural**: Role in structural systems
- **Performative**: Performance characteristics and capabilities

#### 1.4 Cultural/Interpretive Qualia
- **Stylistic**: Artistic and architectural style characteristics
- **Semantic**: Meaning and symbolic significance
- **Value-based**: Historical, artistic, and documentary value
- **Perceptual**: Aesthetic impact and perception

#### 1.5 Contextual Qualia
- **Administrative**: Inventory and institutional management
- **Documentary**: Bibliographic and documentation references
- **Management**: Conservation and intervention history

### 2. Supporting Components

#### 2.1 Document Types
Document types are structured to support the recording and verification of qualia:
- 3D models and spatial surveys
- Images and technical drawings
- Cultural and administrative documentation
- Textual sources and field records

#### 2.2 Extractor Types
Extractors define methods for deriving qualia from documents:
- Measurement and analysis methods
- Cultural and historical interpretation techniques
- Administrative and management procedures

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
