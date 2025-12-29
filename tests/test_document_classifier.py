"""
Unit tests for document classifier.

Tests the rules-based document classification with sample texts
for each supported document type.
"""

import pytest
from nomoros_ai.services.document_classifier import classify_document, get_classification_result


class TestClassifyDocument:
    """Tests for classify_document function."""
    
    def test_title_register_classification(self):
        """Test classification of Title Register documents."""
        sample_text = """
        This official copy is issued by the Land Registry
        Title number: ABC123456
        A: Property Register
        This register describes the land and estate comprised in the title.
        B: Proprietorship Register
        PROPRIETOR: John Smith
        C: Charges Register
        """
        
        doc_type, confidence, method = classify_document(sample_text)
        
        assert doc_type == "TITLE_REGISTER"
        assert confidence >= 0.35
        assert method == "rules_v1"
    
    def test_local_authority_search_classification(self):
        """Test classification of Local Authority Search documents."""
        sample_text = """
        LOCAL AUTHORITY SEARCH
        LLC1 - Official Certificate of Search
        CON29 Enquiries of Local Authority
        
        PLANNING AND BUILDING REGULATIONS
        1.1. Planning decisions and pending applications
        
        ROADS AND PUBLIC RIGHTS OF WAY
        2.1. Roadways, footways and footpaths
        """
        
        doc_type, confidence, method = classify_document(sample_text)
        
        assert doc_type == "LOCAL_AUTHORITY_SEARCH"
        assert confidence >= 0.35
        assert method == "rules_v1"
    
    def test_environmental_search_classification(self):
        """Test classification of Environmental Search documents."""
        sample_text = """
        ENVIRONMENTAL SEARCH REPORT
        
        FLOOD RISK ASSESSMENT
        The property is not within a flood zone.
        
        CONTAMINATED LAND
        No contaminated land registers affect this property.
        
        RADON
        Radon levels in this area are below the action level.
        
        GROUND STABILITY
        No ground stability issues identified.
        """
        
        doc_type, confidence, method = classify_document(sample_text)
        
        assert doc_type == "ENVIRONMENTAL_SEARCH"
        assert confidence >= 0.35
        assert method == "rules_v1"
    
    def test_ta6_classification(self):
        """Test classification of TA6 Property Information Form."""
        sample_text = """
        TA6 - Property Information Form (4th edition)
        
        Seller: Mr John Smith
        Property address: 123 Example Street, London
        
        1. BOUNDARIES
        1.1 Which boundaries belong to this property?
        
        2. DISPUTES AND COMPLAINTS
        2.1 Are there any disputes about this property?
        """
        
        doc_type, confidence, method = classify_document(sample_text)
        
        assert doc_type == "TA6_PROPERTY_INFORMATION_FORM"
        assert confidence >= 0.35
        assert method == "rules_v1"
    
    def test_tr1_classification(self):
        """Test classification of TR1 Transfer Deed."""
        sample_text = """
        TR1 - Transfer of whole of registered title(s)
        
        1. Title number(s) of the property
        2. Property
        
        Transferor: ABC Limited
        Transferee: XYZ Holdings Ltd
        
        Consideration: The sum of 500,000 pounds
        
        Title guarantee: Full title guarantee
        
        Execution: Signed as a deed
        """
        
        doc_type, confidence, method = classify_document(sample_text)
        
        assert doc_type == "TR1_TRANSFER_DEED"
        assert confidence >= 0.35
        assert method == "rules_v1"
    
    def test_lease_classification(self):
        """Test classification of Lease documents."""
        sample_text = """
        LEASE
        
        THIS LEASE is made on the first day of January 2024
        
        BETWEEN:
        (1) Landlord: Property Holdings Ltd
        (2) Tenant: ABC Company Ltd
        
        DEMISE
        The Landlord demises to the Tenant the property
        
        Term: 10 years from 1 January 2024
        
        Rent: 50,000 pounds per annum
        Ground rent: 100 pounds per annum
        """
        
        doc_type, confidence, method = classify_document(sample_text)
        
        assert doc_type == "LEASE"
        assert confidence >= 0.35
        assert method == "rules_v1"
    
    def test_unknown_classification(self):
        """Test classification of unrecognized documents."""
        sample_text = """
        This is a random document with no legal conveyancing content.
        It talks about the weather and sports results.
        Nothing here matches any document type markers.
        """
        
        doc_type, confidence, method = classify_document(sample_text)
        
        assert doc_type == "UNKNOWN"
        assert confidence < 0.35
        assert method == "rules_v1"
    
    def test_low_confidence_returns_unknown(self):
        """Test that low confidence matches return UNKNOWN."""
        sample_text = """
        This document mentions flood risk briefly.
        But nothing else matches any document type.
        """
        
        doc_type, confidence, method = classify_document(sample_text)
        
        if confidence < 0.35:
            assert doc_type == "UNKNOWN"
    
    def test_get_classification_result(self):
        """Test the convenience wrapper function."""
        sample_text = """
        This official copy is issued by the Land Registry
        Title number: XYZ789
        A: Property Register
        """
        
        result = get_classification_result(sample_text)
        
        assert result.document_type == "TITLE_REGISTER"
        assert result.confidence >= 0.35
        assert result.method == "rules_v1"


class TestClassificationConfidence:
    """Tests for confidence scoring."""
    
    def test_more_markers_higher_confidence(self):
        """Test that more matched markers increase confidence."""
        few_markers = "This official copy is issued by the Land Registry"
        many_markers = """
        This official copy is issued by the Land Registry
        Title number: ABC123
        A: Property Register
        B: Proprietorship Register
        C: Charges Register
        HM Land Registry
        Official copy of the register
        """
        
        _, conf_few, _ = classify_document(few_markers)
        _, conf_many, _ = classify_document(many_markers)
        
        assert conf_many > conf_few
    
    def test_confidence_capped_at_one(self):
        """Test that confidence never exceeds 1.0."""
        sample_text = """
        This official copy is issued by the Land Registry
        Title number ABC123
        HM Land Registry
        A: Property Register
        B: Proprietorship Register
        C: Charges Register
        Official copy of the register
        """
        
        _, confidence, _ = classify_document(sample_text)
        
        assert confidence <= 1.0
