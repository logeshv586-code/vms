import React, { useState, useEffect } from 'react';
import { useCameraStore } from '../../store/cameraStore';
import { Monitor as CollectionIcon, Videocam as CctvIcon } from '@mui/icons-material';

const AIDetectionSidebar = ({ isSidebarExpanded = true }) => {
    const { 
        cameras, 
        selectedAiCamera, 
        setSelectedAiCamera, 
        collections, 
        getCamerasByCollection 
    } = useCameraStore();

    const [activeRules, setActiveRules] = useState([]);
    const [allRules, setAllRules] = useState([]);
    const [expandedCollections, setExpandedCollections] = useState({});

    // Auto-select first camera if none is selected
    useEffect(() => {
        if (cameras.length > 0 && !selectedAiCamera) {
            setSelectedAiCamera(cameras[0]);
        }
    }, [cameras, selectedAiCamera, setSelectedAiCamera]);

    // Initialize all collections as expanded by default
    useEffect(() => {
        if (collections.length > 0) {
            const initialExpandedState = {};
            collections.forEach(collection => {
                initialExpandedState[collection.id] = true;
            });
            setExpandedCollections(initialExpandedState);
        }
    }, [collections]);

    // Poll active rules for the selected camera
    useEffect(() => {
        const fetchRules = async () => {
            if (!selectedAiCamera) return;
            try {
                // Fetch all rule definitions if not already loaded
                if (allRules.length === 0) {
                    const rulesResponse = await fetch('/api/augment/events/rules');
                    const rulesData = await rulesResponse.json();
                    if (rulesData.success) {
                        setAllRules(rulesData.data.rules);
                    }
                }

                // Fetch active rules for this specific camera
                const cameraRulesResponse = await fetch('/api/augment/camera-rules');
                const cameraRulesData = await cameraRulesResponse.json();
                if (cameraRulesData.success) {
                    const cameraMap = cameraRulesData.data.cameraRules || {};
                    setActiveRules(cameraMap[selectedAiCamera.id] || []);
                }
            } catch (error) {
                console.error("Error fetching rules in sidebar:", error);
            }
        };

        fetchRules();
        const intervalId = setInterval(fetchRules, 5000);
        return () => clearInterval(intervalId);
    }, [selectedAiCamera, allRules.length]);

    const handleCameraSelect = (camera) => {
        setSelectedAiCamera(camera);
    };

    const toggleCollectionExpand = (collectionId, e) => {
        e.stopPropagation();
        setExpandedCollections(prev => ({
            ...prev,
            [collectionId]: !prev[collectionId]
        }));
    };

    return (
        <div className="ai-detection-sidebar">
            {/* Camera Selection Section */}
            <div className="sidebar-section">
                <div className="sidebar-header">
                    <h4>{isSidebarExpanded ? 'Select Camera' : 'Cameras'}</h4>
                </div>

                {/* Beautiful Collections Tree Layout using exact Universal Sidebar Classes */}
                <ul className="sidebar-menu">
                    {collections.map((collection) => {
                        const collectionCameras = getCamerasByCollection(collection.id);
                        const isCollExp = !!expandedCollections[collection.id];

                        return (
                            <li key={collection.id} className={`submenu-item has-children ${isCollExp ? 'expanded' : ''}`}>
                                <button 
                                    className={`submenu-label ${selectedAiCamera?.collectionId === collection.id ? 'active' : ''}`}
                                    onClick={(e) => toggleCollectionExpand(collection.id, e)}
                                >
                                    <div className="submenu-icon">
                                        <CollectionIcon style={{ color: '#ffca28' }} />
                                    </div>
                                    <span>{collection.name}</span>
                                    {collectionCameras.length > 0 && (
                                        <span className="submenu-count">({collectionCameras.length})</span>
                                    )}
                                    <span className="chevron">▾</span>
                                </button>

                                {isCollExp && (
                                    <ul className="subsubmenu" style={{ maxExpandedHeight: 'none', maxHeight: 'none', display: 'block', opacity: 1 }}>
                                        {collectionCameras.length === 0 ? (
                                            <li className="subsubmenu-item">
                                                <div className="camera-link" style={{ fontStyle: 'italic', opacity: 0.5 }}>
                                                    No cameras
                                                </div>
                                            </li>
                                        ) : (
                                            collectionCameras.map((camera) => {
                                                const isActive = selectedAiCamera?.id === camera.id;
                                                return (
                                                    <li key={camera.id} className="subsubmenu-item">
                                                        <a 
                                                            href="#"
                                                            className={`camera-link ${isActive ? 'active' : ''}`}
                                                            onClick={(e) => {
                                                                e.preventDefault();
                                                                handleCameraSelect(camera);
                                                            }}
                                                        >
                                                            <div className="camera-icon">
                                                                <CctvIcon />
                                                            </div>
                                                            <span className="camera-name">{camera.name}</span>
                                                        </a>
                                                    </li>
                                                );
                                            })
                                        )}
                                    </ul>
                                )}
                            </li>
                        );
                    })}
                </ul>
            </div>

            {/* Active Rules Badges Section */}
            <div className="sidebar-section rules-section">
                <div className="sidebar-header">
                    <h4>Active Rules</h4>
                </div>
                <div className={`rule-badges ${!isSidebarExpanded ? 'collapsed' : ''}`}>
                    {activeRules.length === 0 ? (
                        isSidebarExpanded && <p className="no-rules">No rules applied to this camera.</p>
                    ) : (
                        activeRules
                            .filter(ruleId => {
                                const rule = allRules.find(r => r.id === ruleId);
                                return rule && rule.enabled;
                            })
                            .map(ruleId => {
                                const rule = allRules.find(r => r.id === ruleId);
                                if (!isSidebarExpanded) {
                                    return (
                                        <div key={ruleId} className="active-rule-icon" title={rule?.name}>
                                            <span className="dot active"></span>
                                        </div>
                                    );
                                }
                                return (
                                    <div key={ruleId} className="active-rule-badge">
                                        <span className="dot active"></span>
                                        {rule?.name || `Rule ${ruleId}`}
                                    </div>
                                );
                            })
                    )}
                </div>
            </div>
        </div>
    );
};

export default AIDetectionSidebar;
