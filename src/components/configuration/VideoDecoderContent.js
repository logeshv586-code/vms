import React from 'react';
import VideoDecoderConnector from './decoder/VideoDecoderConnector';
import './VideoDecoderContent.css';

const VideoDecoderContent = ({ selectedMenu }) => {
  // Only render content when Video Decoder Connector menu is selected
  if (selectedMenu !== 'video-decoder-connector') {
    return null;
  }

  return (
    <div className="video-decoder-content">
      <VideoDecoderConnector />
    </div>
  );
};

export default VideoDecoderContent;
