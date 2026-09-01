import React from "react";
import { Container } from "./Container";
import { ContainerWrapper } from "./ContainerWrapper";
import { Div } from "./Div";
import { DivWrapper } from "./DivWrapper";
import group2 from "./group-2.png";
import group3 from "./group-3.png";
import group4 from "./group-4.png";
import group5 from "./group-5.png";
import image from "./image.png";

export const ContainerScreen = () => {
  return (
    <div className="relative w-[1240px] h-[900px] bg-white border-0 border-none">
      <Container />
      <div className="absolute w-[1240px] h-[830px] top-[70px] left-0 bg-white border-0 border-none shadow-[0px_0px_1px_#171a1f12,0px_0px_2px_#171a1f1f]">
        <button className="all-[unset] box-border w-[138px] h-9 top-6 left-[1077px] bg-black rounded-md overflow-hidden absolute border-0 border-none">
          <div className="absolute top-[7px] left-4 [font-family:'Inter-Regular',Helvetica] font-normal text-white text-sm tracking-[0] leading-[22px] whitespace-nowrap">
            2×2 (Quad)
          </div>

          <div className="absolute w-4 h-4 top-2.5 left-[92px]">
            <div className="relative w-[9px] h-[5px] top-[5px] left-[3px]" />
          </div>
        </button>

        <div className="absolute w-[302px] h-[38px] top-[23px] left-[23px] bg-white rounded-md border border-gray-200">
          <div className="absolute top-[7px] left-[34px] [font-family:'Inter-Regular',Helvetica] font-normal text-black text-sm tracking-[0] leading-[22px] whitespace-nowrap">
            Search camera
          </div>

          <div className="absolute w-4 h-4 top-2.5 left-3">
            <div className="relative w-[13px] h-[13px] top-px left-px">
              <div className="h-[13px]">
                <div className="relative w-[13px] h-[13px]">
                  <img
                    className="absolute w-1 h-1 top-[9px] left-[9px]"
                    alt="Group"
                    src={image}
                  />

                  <img
                    className="absolute w-3 h-3 top-0 left-0"
                    alt="Group"
                    src={group2}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        <ContainerWrapper />
        <DivWrapper />
        <Div />
        <div className="absolute w-[584px] h-[340px] top-[448px] left-[632px] bg-gray-100 rounded-md border border-gray-200">
          <div className="relative w-[552px] h-[280px] top-[30px] left-4 bg-white rounded-md border border-gray-200">
            <div className="absolute w-12 h-12 top-[102px] left-[252px]">
              <div className="relative w-11 h-10 top-1 left-0.5">
                <div className="h-10">
                  <div className="relative w-11 h-10">
                    <img
                      className="absolute w-11 h-8 top-0 left-0"
                      alt="Group"
                      src={group3}
                    />

                    <img
                      className="absolute w-5 h-1 top-9 left-3"
                      alt="Group"
                      src={group4}
                    />

                    <img
                      className="absolute w-1 h-3 top-7 left-5"
                      alt="Group"
                      src={group5}
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="absolute top-40 left-[183px] [font-family:'Inter-Regular',Helvetica] font-normal text-black text-sm tracking-[0] leading-5 whitespace-nowrap">
              No Camera Feed Available
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
