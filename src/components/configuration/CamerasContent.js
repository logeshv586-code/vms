import React, { useState } from 'react';
import AddCollectionModal from './AddCollectionModal';
import AddCameraModal from './AddCameraModal';
import CameraTable from './CameraTable';
import addIcon from '../../icon/add-icon.png';
import { useUserStore } from '../../store/userStore';
import './CamerasContent.css';

const CamerasContent = ({ selectedMenu }) => {
  const [showAddCollectionModal, setShowAddCollectionModal] = useState(false);
  const [showAddCameraModal, setShowAddCameraModal] = useState(false);
  const { currentUser } = useUserStore();

  // Check if user is supervisor
  const isSupervisor = currentUser?.role === 'Supervisor';

  // Only render content when Cameras menu is selected
  if (selectedMenu !== 'cameras') {
    return null;
  }

  return (
    <div className="cameras-content">
      <div className="content-toolbar">
        <div className="toolbar-title">
          <h2>Configuration › Cameras</h2>
        </div>
        {!isSupervisor && (
          <div className="toolbar-actions">
            <button
              className="add-collection-button"
              onClick={() => setShowAddCollectionModal(true)}
              aria-label="Manage Collection"
              aria-haspopup="dialog"
            >
              <img src={addIcon} alt="" className="button-icon" aria-hidden="true" />
              <span>Manage Collection</span>
            </button>
            <button
              className="add-camera-button"
              onClick={() => setShowAddCameraModal(true)}
              aria-label="Add New Camera"
              aria-haspopup="dialog"
            >
              <img src={addIcon} alt="" className="button-icon" aria-hidden="true" />
              <span>Add New Camera</span>
            </button>
          </div>
        )}
      </div>

      <div className="cameras-content-main">
        <CameraTable />
      </div>

      {showAddCollectionModal && (
        <AddCollectionModal onClose={() => setShowAddCollectionModal(false)} />
      )}
      {showAddCameraModal && (
        <AddCameraModal onClose={() => setShowAddCameraModal(false)} />
      )}
    </div>
  );
};

export default CamerasContent;