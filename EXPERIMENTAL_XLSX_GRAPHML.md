# XLSX → GraphML Converter - Experimental Feature

## Overview

The XLSX → GraphML converter is an **experimental feature** in EM-blender-tools that transforms AI-extracted stratigraphic data from Excel spreadsheets into Extended Matrix GraphML format.

## Status: Experimental ⚠️

This feature is marked as experimental and should be used with caution:
- Data fidelity may vary
- Not intended for production use without verification
- Always validate generated GraphML in yEd before importing

## Location in UI

**Requires Experimental Features to be enabled:**

1. Open EM Setup panel
2. Expand "Utilities & Settings" section
3. Enable "Experimental" toggle
4. The "Experimental tools" section will appear
5. Click "XLSX → GraphML (AI Data)" button

## How It Works

The converter implements a three-stage transformation pipeline:

### Stage 1: Excel (Tabular Data)
- Human-readable spreadsheet format
- Columns for stratigraphic units and relationships
- Special columns: EXTRACTOR, DOCUMENT (for AI provenance tracking)

### Stage 2: s3dgraphy (Extended Graph)
- Internal graph representation
- Nodes with 3D capabilities + EM concepts
- EXTRACTOR/DOCUMENT stored as **attributes** on StratigraphicNode
- Groups "dissolved" into individual nodes

### Stage 3: Extended Matrix GraphML (Hypergraph)
- yEd-compatible GraphML format
- ParadataNodeGroup containers
- EXTRACTOR/DOCUMENT transformed into separate ExtractorNode/DocumentNode
- Complete paradata structure with provenance chains

## Transformation Details

### Attribute → Node Transformation

The GraphMLExporter performs critical transformations during export:

**In Excel/s3dgraphy:**
```
StratigraphicNode(USM01)
  ├─ extractor: "GPT-4"      (attribute)
  └─ document: "Report_2023.pdf"  (attribute)
```

**In Extended Matrix GraphML:**
```
StratigraphicNode(USM01)                    [n0::n1]
    ↓ has_paradata_nodegroup (dashed edge)
ParadataNodeGroup(USM01_PD)                 [n0::n10]  backgroundColor="#FFCC99"
    ├─ PropertyNode(stratigraphic_definition) [n0::n10::n0]
    │   ↓ has_data_provenance
    │   ExtractorNode(D.GPT4)                 [n0::n10::n1]  SVG icon
    │       ↓ extracted_from
    │       DocumentNode(Report_2023.pdf)     [n0::n10::n2]  BPMN Data Object
```

### Node Types and Visual Representation

**ExtractorNode:**
- Family: Paradata (NOT PropertyNode)
- Visual: SVG node with icon
- Label: "D." (Data extractor) or "C." (Combiner)
- Color: #CCCCFF background

**DocumentNode:**
- Family: Paradata (NOT PropertyNode)
- Visual: BPMN Data Object shape
- Label: Document filename
- Color: #FFFFFFE6 background

**ParadataNodeGroup:**
- Background color: #FFCC99
- Border: Dashed line
- Collapsible: Two realizers (open/closed states)
- Connected to US with dashed directional edge

## Excel Template Format

### Required Columns

| Column | Type | Description |
|--------|------|-------------|
| ID | Identifier | Stratigraphic unit ID (US/USM/USV/SF) |
| TYPE | Property | Unit type (US, USVs, USVn, SF, etc.) |
| DESCRIPTION | Property | Textual description |
| PERIOD | Epoch | Historical period |
| PHASE | Epoch | Chronological phase |
| EXTRACTOR | Attribute | Who/what extracted data (GPT-4, Claude, Manual) |
| DOCUMENT | Attribute | Source document reference (filename.pdf) |

### Relationship Columns

- OVERLIES, OVERLAIN_BY
- CUTS, CUT_BY
- FILLS, FILLED_BY
- ABUTS, ABUTTED_BY
- BONDED_TO
- EQUALS

## Usage Example

### 1. Prepare Excel File

Create spreadsheet with AI-extracted data:

```
ID    | TYPE | DESCRIPTION              | EXTRACTOR | DOCUMENT
------|------|-------------------------|-----------|------------------
USM01 | US   | Compact earth layer     | GPT-4     | Report_2023.pdf
USM02 | US   | Foundation wall         | Claude    | FieldNotes_Day5.pdf
USV100| USVs | Negative surface        | Manual    | Survey_2024.pdf
```

### 2. Run Converter

1. Enable Experimental Features in EM Setup
2. Click "XLSX → GraphML (AI Data)"
3. Select Excel file
4. Specify mapping name (default: `excel_to_graphml_mapping`)
5. Set output filename
6. Execute conversion

### 3. Verify Output

**Always verify** the generated GraphML:
1. Open output.graphml in yEd
2. Check node shapes match types (US=rectangle, USVs=parallelogram, etc.)
3. Verify ParadataNodeGroup background color (#FFCC99)
4. Confirm ExtractorNode/DocumentNode icons visible
5. Test collapsing/expanding ParadataNodeGroups
6. Validate edges and relationships

## Technical Implementation

### Components

**s3dgraphy modules:**
- `MappedXLSXImporter` - Excel → s3dgraphy graph
- `GraphMLExporter` - s3dgraphy → Extended Matrix GraphML
- `NodeRegistry` - Hybrid node definitions (JSON datamodel + palette template)

**Key files:**
- `/operators/xlsx_to_graphml.py` - Blender operator
- `/src/s3dgraphy/exporter/graphml/graphml_exporter.py` - Main exporter
- `/src/s3dgraphy/mappings/generic/excel_to_graphml_mapping.json` - Mapping configuration

### Mapping Configuration

The mapping JSON defines how Excel columns transform to s3dgraphy nodes:

```json
{
  "EXTRACTOR": {
    "node_type": "StratigraphicNode",
    "property_name": "extractor",
    "is_attribute": true,
    "description": "Stored as attribute on StratigraphicNode. During GraphML export, transformed into ExtractorNode within ParadataNodeGroup."
  }
}
```

### GraphML Export Process

The `_build_paradata_groups()` method in GraphMLExporter:

1. Iterates through StratigraphicNodes
2. Reads `extractor` and `document` attributes
3. Creates ParadataNodeGroup structure
4. Generates PropertyNode(stratigraphic_definition)
5. Creates ExtractorNode with SVG icon
6. Creates DocumentNode with BPMN Data Object shape
7. Connects with proper edges (dashed)

## Use Cases

### AI-Assisted Stratigraphic Documentation

**Scenario:** Archaeological team has 50+ PDF reports needing digitization.

**Workflow:**
1. Use AI (GPT-4, Claude) to extract stratigraphic data from PDFs
2. AI populates Excel template with extracted information
3. AI fills EXTRACTOR column with its name (e.g., "GPT-4")
4. AI fills DOCUMENT column with source PDF filename
5. Run XLSX → GraphML converter
6. Verify output in yEd
7. Import into Blender via EM Setup

**Benefits:**
- Automatic provenance tracking
- Traceability to source documents
- Clear indication of AI vs manual data entry
- Paradata structure for transparency

### Hybrid Manual-AI Workflows

**Scenario:** Mix of manually excavated units and AI-extracted historical data.

**Workflow:**
1. Manual field data: EXTRACTOR="Manual", DOCUMENT="FieldBook_2024.pdf"
2. AI-extracted data: EXTRACTOR="Claude", DOCUMENT="Archive_Report_1985.pdf"
3. Combine in single Excel file
4. Convert to GraphML
5. Visual distinction in paradata (manual vs AI extractors)

## Known Limitations

### Experimental Status Issues

1. **Edge Case Handling:** Complex stratigraphic relationships may not convert perfectly
2. **Validation:** Limited validation of Excel data before conversion
3. **Error Recovery:** Conversion failures may not provide detailed diagnostics
4. **Performance:** Large datasets (>1000 units) not thoroughly tested

### Data Fidelity Concerns

1. **Topological Completeness:** Ensure all stratigraphic relationships are captured
2. **Epoch Inference:** Temporal information may need manual verification
3. **Type Mapping:** Unusual unit types may default to generic representation
4. **Unicode Handling:** Special characters in descriptions need testing

### Visual Verification Required

Always check in yEd:
- Node colors match types
- ParadataNodeGroup backgroundColor = #FFCC99 (NOT #CCFFFF)
- ExtractorNode shows correct icon (D. or C.)
- DocumentNode renders as BPMN Data Object
- Edges have correct line styles (dashed for paradata)

## Troubleshooting

### Common Issues

**Problem:** Conversion fails with "Mapping file not found"

**Solution:** Verify mapping name. Available mappings:
- `excel_to_graphml_mapping` (default, AI data collection)
- `usm_mapping` (USM-focused)
- `pyarchinit_us_mapping` (PyArchInit compatibility)

---

**Problem:** ParadataNodeGroups have wrong color in yEd

**Solution:** This is a critical bug. ParadataNodeGroup MUST have backgroundColor="#FFCC99". If showing #CCFFFF (cyan), that's ActivityNodeGroup color. Report as bug.

---

**Problem:** ExtractorNode/DocumentNode missing in output

**Solution:** Check Excel file has EXTRACTOR/DOCUMENT columns filled. Empty values won't generate paradata structures.

---

**Problem:** yEd crashes or shows errors when opening GraphML

**Solution:**
1. Validate XML syntax: `xmllint --noout output.graphml`
2. Check for invalid characters in descriptions
3. Verify all node IDs are unique
4. Ensure nested ID format correct (n0::n1, not n0.n1)

---

**Problem:** Stratigraphic relationships not showing correctly

**Solution:** Verify Excel relationship columns use comma-separated IDs:
- Correct: "USM02,USM03,USM05"
- Incorrect: "USM02; USM03; USM05" (wrong separator)

## Best Practices

### Before Conversion

1. **Validate Excel Data:**
   - Check all required columns present
   - Verify ID uniqueness
   - Ensure relationship IDs reference existing units
   - Test with small subset first (10-20 units)

2. **Document Provenance:**
   - Fill EXTRACTOR column consistently (e.g., "GPT-4", "Claude-3.5", "Manual")
   - Use full filenames in DOCUMENT column with extensions
   - Add date/version info if multiple document versions exist

3. **Type Consistency:**
   - Use standard TYPE values from EM formalism
   - Valid: US, USVs, USVn, SF, VSF, USD, serSU, serUSVn, serUSVs, TSU, SE, BR
   - Avoid: Custom types without mapping configuration

### After Conversion

1. **Visual Inspection in yEd:**
   - Open GraphML in yEd immediately
   - Check first 5-10 nodes visually match expected types
   - Verify at least one ParadataNodeGroup renders correctly
   - Test collapsing/expanding groups

2. **Structural Validation:**
   - Run yEd's "Tools > Fit Node to Label" to check label visibility
   - Use "Tools > Check Consistency" to find orphaned nodes
   - Verify no red error indicators on nodes

3. **Backup Original:**
   - Keep Excel source file alongside GraphML
   - Document any manual corrections made in yEd
   - Version control both files if in team environment

### Production Use

**DO NOT use directly in production projects without:**
1. Full visual verification in yEd
2. Test import into Blender with small dataset
3. Validation of all stratigraphic relationships
4. Manual review of AI-extracted descriptions
5. Cross-reference with original source documents

## Future Development

### Planned Improvements

- [ ] Pre-conversion validation with detailed error messages
- [ ] Excel template generator with example data
- [ ] Batch conversion for multiple files
- [ ] Automatic temporal inference from relationships
- [ ] Integration with AI extraction tools (direct API)
- [ ] Visual diff tool (Excel vs GraphML)
- [ ] Automated testing suite with reference datasets

### Feedback and Bug Reports

This is an **experimental feature** - your feedback is essential:

**Report issues with:**
- Excel file structure (anonymized if sensitive)
- Error messages and tracebacks
- Generated GraphML file (anonymized)
- Screenshots of yEd rendering issues
- Expected vs actual behavior

**Repository:** s3dgraphy and EM-blender-tools GitHub repos

## References

### Documentation

- **EM Formalism:** Extended Matrix documentation
- **s3dgraphy:** Data formalization guide (DATA_FORMALIZATIONS.md)
- **GraphML Export:** Technical documentation (GRAPHML_EXPORT.md)
- **Node Datamodel:** s3Dgraphy_node_datamodel.json
- **Connections Datamodel:** s3Dgraphy_connections_datamodel.json

### Related Tools

- **yEd Graph Editor:** https://www.yworks.com/products/yed
- **Extended Matrix Palette:** EM palette v.1.5dev6 template
- **Blender:** https://www.blender.org/

---

**Version:** 1.0 (Experimental)
**Last Updated:** 2024-02-08
**Status:** Experimental - Use with caution and verification
